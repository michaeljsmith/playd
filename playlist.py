#!/usr/bin/env python3.1

from threading import Thread, Lock, Semaphore
from time import sleep
from sys import stdin

def trace(x):
	#print(x)
	pass

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
			trace('Queue listen thread started.')

			while True:
				x = self.in_queue.pop()
				if not x: break
				trace('Queue listen thread found item (' + x + ')')
				self.out_queue.append(x)
				self.semaphore.release()

			trace('Queue listen thread ended.')

	class ActionThread(Thread):
		def __init__(self, action, arg, oob_queue, semaphore):
			super().__init__()
			self.action = action
			self.arg = arg
			self.oob_queue = oob_queue
			self.semaphore = semaphore

		def run(self):
			trace('Action (' + self.arg + ') started.')
			self.action(self.arg)
			trace('Action (' + self.arg + ') ended.')
			self.oob_queue.append(('finished',))
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
		trace('Play thread started.')

		while True:
			self.semaphore.acquire()
			if len(self.oob_queue):
				cmd = self.oob_queue.pop()
				if cmd[0] == 'finished':
					trace('Play thread got command (' + cmd[0] + ')')
					self.action_thread.join()
					self.action_thread = None
				elif cmd[0] == 'exit':
					trace('Play thread got command (' + cmd[0] + ')')
					self.queue.append(None)
					self.queue_listen_thread.join()
					break
				else:
					trace('Play thread got UNKNOWN command (' + cmd[0] + ')')
			if not self.action_thread and len(self.file_queue):
				x = self.file_queue.pop()
				trace('Play thread performing new item (' + x + ')')
				self.action_thread = PlayThread.ActionThread(
						self.action, x, self.oob_queue, self.semaphore)
				self.action_thread.start()

		trace('Play thread ended.')

	def exit(self):
		self.oob_queue.append(('exit',))
		self.semaphore.release()

class ReadThread(Thread):

	def __init__(self, queue, input):
		super().__init__()
		self.queue = queue
		self.input = input

	def run(self):
		trace('Read thread started.')
		for line in self.input:
			self.queue.append(line.strip())
		trace('Read thread ended.')

def action(x):
	sleep(1.0)
	print(x)

def main():
	trace('Main thread started.')
	items = ThreadDataQueue()
	play_thread = PlayThread(action, items)
	trace('Main thread launching play thread.')
	play_thread.start()
	read_thread = ReadThread(items, stdin)
	trace('Main thread launching read thread.')
	read_thread.start()
	trace('Main thread joining read thread.')
	read_thread.join()
	trace('Main thread exiting play thread.')
	play_thread.exit()
	trace('Main thread joining play thread.')
	play_thread.join()
	trace('Main thread ended')

if __name__ == '__main__':
	main()

