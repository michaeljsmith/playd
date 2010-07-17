#!/usr/bin/env python3.1

from threading import Thread, Lock, Semaphore
from time import sleep
from sys import stdin

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

	def __len__(self):
		self.lock.acquire()
		l = -1
		try:
			l = len(self.items)
		finally:
			self.lock.release()
		return l

class PlayThread(Thread):

	class QueueListenThread(Thread):
		def __init__(self, in_queue, out_queue, semaphore):
			super().__init__()
			self.in_queue = in_queue
			self.out_queue = out_queue
			self.semaphore = semaphore

		def run(self):
			while True:
				x = self.in_queue.pop()
				if not x: break
				self.out_queue.append(x)
				self.semaphore.release()

	class ActionThread(Thread):
		def __init__(self, action, arg, oob_queue, semaphore):
			super().__init__()
			self.action = action
			self.arg = arg
			self.oob_queue = oob_queue
			self.semaphore = semaphore

		def run(self):
			self.action(self.arg)
			self.oob_queue.append(('finished'))
			self.semaphore.release()

	def __init__(self, action, queue):
		super().__init__()
		self.action = action
		self.semaphore = Semaphore(0)
		self.file_queue = ThreadDataQueue()
		self.oob_queue = ThreadDataQueue()
		self.queue = queue
		self.queue_listen_thread = PlayThread.QueueListenThread(queue, self.file_queue, self.semaphore)
		self.queue_listen_thread.start()
		self.action_thread = None

	def run(self):
		while True:
			self.semaphore.acquire()
			if len(self.oob_queue):
				cmd = self.oob_queue.pop()
				if cmd[0] == 'finished':
					self.action_thread.join()
					self.action_thread = None
				elif cmd[0] == 'exit':
					self.queue.append(None)
					self.queue_listen_thread.join()
					break
			elif not self.action_thread:
				x = self.file_queue.pop()
				self.action_thread = PlayThread.ActionThread(
						self.action, x, self.oob_queue, self.semaphore)
				self.action_thread.start()

	def exit(self):
		self.oob_queue.append(('exit'))
		self.semaphore.release()

class ReadThread(Thread):

	def __init__(self, queue, input):
		super().__init__()
		self.queue = queue
		self.input = input

	def run(self):
		for line in self.input:
			self.queue.append(line)

def action(x):
	sleep(1.0)
	print(x)

def main():
	items = ThreadDataQueue()
	play_thread = PlayThread(action, items)
	play_thread.start()
	read_thread = ReadThread(items, stdin)
	read_thread.start()
	read_thread.join()
	play_thread.exit()
	play_thread.join()

if __name__ == '__main__':
	main()

