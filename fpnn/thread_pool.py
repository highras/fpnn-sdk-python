import sys
if sys.version > '3':
    import queue
else:
    import Queue as queue
import os
import threading
import contextlib
import time

StopEvent = object()

class ThreadPool(object):
    def __init__(self, max_num = None, max_task_num = None):
        if max_task_num:
            self.q = queue.Queue(max_task_num)
        else:
            self.q = queue.Queue()
        if max_num == None:
            max_num = (os.cpu_count() or 1) * 5
        self.max_num = max_num
        self.cancel = False
        self.terminal = False
        self.generate_list = []
        self.free_list = []

    def run(self, func, args, callback=None):
        if self.cancel:
            return
        if len(self.free_list) == 0 and len(self.generate_list) < self.max_num:
            self.generate_thread()
        w = (func, args, callback,)
        self.q.put(w)

    def generate_thread(self):
        t = threading.Thread(target=self.call)
        t.start()

    def call(self):
        current_thread = threading.currentThread()
        self.generate_list.append(current_thread)

        event = self.q.get()
        while event != StopEvent:

            func, arguments, callback = event
            try:
                result = func(*arguments)
                success = True
            except Exception as e:
                success = False
                result = None

            if callback is not None:
                try:
                    callback(success, result)
                except Exception as e:
                    pass

            with self.worker_state(self.free_list, current_thread):
                if self.terminal:
                    event = StopEvent
                else:
                    event = self.q.get()
        else:
            self.generate_list.remove(current_thread)

    def close(self):
        self.cancel = True
        full_size = len(self.generate_list) + 1
        while full_size:
            self.q.put(StopEvent)
            full_size -= 1

    def terminate(self):
        self.terminal = True

        while self.generate_list:
            self.q.put(StopEvent)

        self.q.queue.clear()

    @contextlib.contextmanager
    def worker_state(self, state_list, worker_thread):
        state_list.append(worker_thread)
        try:
            yield
        finally:
            state_list.remove(worker_thread)