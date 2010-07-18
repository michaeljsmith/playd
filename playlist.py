#!/usr/bin/env python3.1

from threading import Thread, Condition
from time import sleep
from sys import argv
from os.path import basename, abspath, join
from os import environ

class PlaydError(Exception): pass
class NoActionError(PlaydError): pass

def trace(x):
	print(x)

class PlayThread(Thread):

	def __init__(self, action_performer):
		super().__init__()
		self.action_performer = action_performer
		self._queue = []
		self.exit_pending = False
		self.action = None
		self.condition = Condition()

	def run(self):
		trace('Play thread started.')

		action_running = [False]

		self.condition.acquire()
		try:
			while True:
				def on_action_finished():
					self.condition.acquire()
					try:
						action_running[0] = False
						self.condition.notify_all()
					finally:
						self.condition.release()

				if self.exit_pending:
					if action_running[0]:
						trace('Play thread cancelling action.')
						self.action.cancel()
					break

				if not action_running[0]:
					if self._queue:
						x = self._queue.pop(0)
						trace('Play threading performing action (' + x + ')')
						self.action = self.action_performer(x,
								on_action_finished, on_action_finished)
						action_running[0] = True
					else:
						trace('Play thread waiting for input.')
						self.action = None

				trace('Play thread waiting.')
				self.condition.wait()
				trace('Play thread woken.')
		finally:
			self.condition.release()

		if self.action:
			trace('Play thread exiting, waiting for action to shutdown.')
			self.action.wait()

		trace('Play thread ended.')

	def exit(self):
		trace('Cancelling play thread.')
		self.condition.acquire()
		try:
			self._queue[:] = [None]
			self.exit_pending = True
			self.condition.notify_all()
		finally:
			self.condition.release()

		trace('Waiting for play thread.')
		self.join()
		trace('Finished waiting for play thread.')

	def queue(self, x):
		trace('Queueing (' + x + ') on play thread.')
		self.condition.acquire()
		try:
			self._queue.append(x)
			self.condition.notify_all()
		finally:
			self.condition.release()

	def next(self):
		trace('Skipping action.')
		self.condition.acquire()
		action = self.action
		try:
			if not action:
				raise NoActionError()

			action.cancel()
		finally:
			self.condition.release()
		trace('Skipping action cancel issued, waiting for action to shutdown.')
		if action:
			self.action.wait()
		trace('Skipping action finished.')

class ActionPerformer(object):

	class ActionThread(Thread):

		def __init__(self, x, condition, on_finished, on_cancelled):
			super().__init__()
			self.x = x
			self.condition = condition
			self.cancelled = False
			self.on_finished = on_finished
			self.on_cancelled = on_cancelled

		def run(self):
			self.condition.acquire()
			try:
				self.condition.wait(8.0)
				if not self.cancelled:
					print('out: ' + self.x)
			finally:
				self.condition.release()
			if self.cancelled:
				self.on_cancelled()
			else:
				self.on_finished()

		def cancel(self):
			self.condition.acquire()
			try:
				self.cancelled = True
				self.condition.notify_all()
			finally:
				self.condition.release()

	def __init__(self, x, on_finished, on_cancelled):
		self.condition = Condition()
		self.thread = self.ActionThread(x, self.condition, on_finished, on_cancelled)
		self.thread.start()

	def cancel(self):
		self.thread.cancel()

	def wait(self):
		self.thread.join()

def main():
	trace('Main thread started.')
	play_thread = PlayThread(ActionPerformer)
	trace('Main thread launching play thread.')
	play_thread.start()

	home = environ['HOME']
	input_filename = abspath(join(home, basename(argv[0])))

	while True:
		try:
			input = open(input_filename, 'r')
		except IOError as err:
			print('Unable to open input file: ' + input_filename + ': ' + str(err))
			break

		command = input.readline().strip()
		if command == 'exit':
			break
		if command == 'next':
			try:
				play_thread.next()
			except NoActionError:
				print('No action playing to skip.')
		elif command == 'play':
			for line in input:
				if line[-1] == '\n':
					line = line[:-1]
				play_thread.queue(line)
		else:
			print('Unknown command received: ' + command)

	trace('Main thread exiting play thread.')
	play_thread.exit()
	trace('Main thread ended')

if __name__ == '__main__':
	main()
