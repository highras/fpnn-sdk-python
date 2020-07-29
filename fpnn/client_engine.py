#encoding=utf8

import os
import time
import errno
import threading
import selectors
import socket
from concurrent.futures import ThreadPoolExecutor
from .thread_pool import *

class ReadySocketInfo(object):
    def __init__(self, sock, read, write):
        self.socket = sock
        self.can_read = read
        self.can_write = write

class ClientEngine(object):
    _instance_lock = threading.Lock()
    error_recorder = None

    def __new__(cls, *args, **kw):
        if not hasattr(ClientEngine, "_instance"):
            with ClientEngine._instance_lock:
                if not hasattr(ClientEngine, "_instance"):
                    ClientEngine._instance = object.__new__(cls)  
                    ClientEngine._instance.init()
        return ClientEngine._instance

    def __init__(self):
        pass

    def init(self):
        self.running = True
        self.loop_thread = None
        self.lock = threading.Lock()
        self.want_write_lock = threading.Lock()
        self.thread_pool_executor = ThreadPool()
        self.notify_lock = threading.Lock()
        self.read_notify_fd, self.write_notify_fd = os.pipe()
        os.set_blocking(self.read_notify_fd, False)
        os.set_blocking(self.write_notify_fd, False)
        self.read_notify = os.fdopen(self.read_notify_fd)
        self.write_notify = os.fdopen(self.write_notify_fd, 'w')
        self.connection_map = {}
        self.new_socket_set = set()
        self.quit_socket_set = set()
        self.want_write_socket_set = set()
        self.loop_thread = threading.Thread(target=ClientEngine.loop, args=(self,))
        self.loop_thread.setDaemon(True)
        self.loop_thread.start()
        self.check_thread = threading.Thread(target=ClientEngine.check, args=(self,))
        self.check_thread.setDaemon(True)
        self.check_thread.start()

    def stop(self):
        self.running = False
        self.next_loop()
        if self.loop_thread != None:
            self.loop_thread.join()
        if self.check_thread != None:
            self.check_thread.join()
        self.read_notify.close()
        self.write_notify.close()

    def check(self):
        while self.running:
            cyc = 10
            while self.running:
                cyc -= 1
                if cyc == 0:
                    break
                time.sleep(0.1)
            self.check_timeout()

    def check_timeout(self):
        with self.lock:
            for (socket_fd, connection) in  self.connection_map.items(): 
                connection.check_timeout()

    def thread_pool_execute(self, fn, args):
        self.thread_pool_executor.run(fn, args)

    def loop(self):
        selector = selectors.DefaultSelector()

        selector.register(
            self.read_notify_fd,
            selectors.EVENT_READ,
        )

        all_socket = set()
        want_write_socket = set()
        
        while self.running:
            with self.lock:
                for s in all_socket:
                    if s in self.quit_socket_set:
                        continue
                    try:
                        selector.unregister(s)
                    except KeyError:
                        pass
                    if s in want_write_socket:
                        selector.register(
                            s,
                            selectors.EVENT_READ | selectors.EVENT_WRITE,
                        )
                    else:
                        selector.register(
                            s,
                            selectors.EVENT_READ,
                        )

            ready_socket_set = set()
            for key, mask in selector.select():
                if key.fileobj == self.read_notify_fd:
                    self.consume_notify()

                if not self.running:
                    break

                canRead = False
                canWrite = False
                if mask & selectors.EVENT_READ and key.fileobj != self.read_notify_fd:
                    canRead = True

                if mask & selectors.EVENT_WRITE and key.fileobj != self.read_notify_fd:
                    canWrite = True
                
                if canRead or canWrite:
                    ready_socket_set.add(ReadySocketInfo(key.fileobj, canRead, canWrite))

            if not self.running:
                break

            for s in ready_socket_set:
                self.process_connection_io(s)

            with self.lock:
                if len(self.new_socket_set) > 0:
                    all_socket.update(self.new_socket_set)
                    self.new_socket_set.clear()

                if len(self.quit_socket_set) > 0:
                    for s in self.quit_socket_set:
                        all_socket.remove(s)
                    self.quit_socket_set.clear()

            with self.want_write_lock:
                want_write_socket.clear()
                if len(self.want_write_socket_set) > 0:
                    want_write_socket.update(self.want_write_socket_set)

    def process_connection_io(self, si):
        with self.lock:
            connection = self.connection_map.get(si.socket, None)
            if connection != None:
                connection.process_io(si.can_read, si.can_write)

    def join(self, connection):
        with self.lock:
            self.connection_map[connection.socket] = connection
            self.new_socket_set.add(connection.socket)
        self.next_loop()

    def quit(self, connection):
        if connection == None:
            return
        with self.lock:
            del self.connection_map[connection.socket]
            self.quit_socket_set.add(connection.socket)
        self.next_loop()

    def quit_in_loop(self, connection):
        # no lock for run in IO loop thread
        if connection == None:
            return
        del self.connection_map[connection.socket]
        self.quit_socket_set.add(connection.socket)
        self.next_loop()

    def require_write(self, connection):
        with self.want_write_lock:
            self.want_write_socket_set.add(connection.socket)
        self.next_loop() 

    def release_write(self, connection):
        with self.want_write_lock:
            try:
                self.want_write_socket_set.remove(connection.socket)
                self.next_loop()
            except KeyError:
                pass
        
    def next_loop(self):
        with self.notify_lock:
            self.write_notify.write("0")
            self.write_notify.flush()

    def consume_notify(self):
        while True:
            try:
                os.read(self.read_notify_fd, 1)
            except BlockingIOError as error:
                if ClientEngine.error_recorder != None:
                    ClientEngine.error_recorder.record_error("consume notify got BlockingIOError")
                break
            except IOError as error:
                if error.errno == errno.EAGAIN or error.errno == errno.EWOULDBLOCK or error.errno == errno.EINTR:
                    continue
                else:
                    if ClientEngine.error_recorder != None:
                        ClientEngine.error_recorder.record_error("consume notify got error: " + error.errno)
                    break


