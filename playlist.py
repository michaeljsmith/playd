#!/usr/bin/env python3.1

from threading import Thread, Lock, Semaphore
from time import sleep

class ThreadDataQueue(object):
	def __init__(self):
		self.items = []
		self.lock = Lock()
		self.semaphore = Semaphore(0)

	def append(self, message):
		self.lock.acquire()
		try:
			self.items.append(message)
			self.semaphore.release()
		finally:
			self.lock.release()

	def pop(self):
		self.semaphore.acquire()
		self.lock.acquire()
		message = None
		try:
			message = self.items.pop(0)
		finally:
			self.lock.release()
		return message

class PlayThread(Thread):

	def __init__(self, queue):
		super().__init__()
		self.queue = queue

	def run(self):
		while True:
			x = self.queue.pop()
			print(x)

class ReadThread(Thread):

	def __init__(self, queue):
		super().__init__()
		self.queue = queue

	def run(self):
		a = 0
		while True:
			sleep(1.0)
			self.queue.append(str(a))
			a += 1

def main():
	items = ThreadDataQueue()
	play_thread = PlayThread(items)
	play_thread.start()
	read_thread = ReadThread(items)
	read_thread.start()
	play_thread.join()
	read_thread.join()

if __name__ == '__main__':
	main()

