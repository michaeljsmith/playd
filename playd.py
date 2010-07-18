#!/usr/bin/env python3.1

from threading import Thread, Condition
from time import sleep
from sys import argv
from os.path import basename, abspath, join
from os import environ, mkfifo, remove, access, F_OK
from subprocess import Popen

class PlaydError(Exception): pass
class NoActionError(PlaydError): pass
class CmdLineError(PlaydError): pass
class FifoMissingError(PlaydError): pass

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

class ChildProcessActionPerformer(object):

	class ActionThread(Thread):

		def __init__(self, arg, on_finished, on_cancelled):
			super().__init__()
			self.cancelled = False
			self.on_finished = on_finished
			self.on_cancelled = on_cancelled
			self.process = Popen(['mplayer', arg])

		def run(self):
			self.process.wait()
			if self.cancelled:
				self.on_cancelled()
			else:
				self.on_finished()

		def cancel(self):
			self.cancelled = True
			self.process.terminate()

	def __init__(self, x, on_finished, on_cancelled):
		self.condition = Condition()
		self.thread = self.ActionThread(x, on_finished, on_cancelled)
		self.thread.start()

	def cancel(self):
		self.thread.cancel()

	def wait(self):
		self.thread.join()

class Command(object):
	pass

class StartCommand(Command):
	def __init__(self, fifo_path):
		self.fifo_path = fifo_path

	def perform(self):
		trace('Main thread started.')
		try:
			mkfifo(self.fifo_path)
		except OSError as err:
			print('Unable to create command fifo: ' + self.fifo_path + ': ' + str(err))
			return

		try:
			play_thread = PlayThread(ChildProcessActionPerformer)
			trace('Main thread launching play thread.')
			play_thread.start()

			try:
				while True:
					try:
						input = open(self.fifo_path, 'r')
					except IOError as err:
						print('Unable to open command fifo: ' + self.fifo_path + ': ' + str(err))
						break

					try:
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
					finally:
						input.close()

			finally:
				trace('Main thread exiting play thread.')
				play_thread.exit()
				trace('Main thread ended')
		finally:
			remove(self.fifo_path)

class StopCommand(Command):
	def __init__(self, fifo_path):
		self.fifo_path = fifo_path

	def perform(self):
		try:
			if not access(self.fifo_path, F_OK):
				raise FifoMissingError('file does not exist')
			output = open(self.fifo_path, 'w')
			try:
				output.write('exit\n')
			finally:
				output.close()
		except IOError as err:
			print('Unable to open command fifo: ' + self.fifo_path + ': ' + str(err))

class QueueCommand(Command):
	def __init__(self, fifo_path, items):
		self.fifo_path = fifo_path
		self.items = items

	def perform(self):
		try:
			if not access(self.fifo_path, F_OK):
				raise FifoMissingError('file does not exist')
			output = open(self.fifo_path, 'w')
			try:
				output.write('play\n')
				for item in self.items:
					output.write(item + '\n')
			finally:
				output.close()
		except IOError as err:
			print('Unable to open command fifo: ' + self.fifo_path + ': ' + str(err))

class NextCommand(Command):
	def __init__(self, fifo_path):
		self.fifo_path = fifo_path

	def perform(self):
		try:
			if not access(self.fifo_path, F_OK):
				raise FifoMissingError('file does not exist')
			output = open(self.fifo_path, 'w')
			try:
				output.write('next\n')
			finally:
				output.close()
		except IOError as err:
			print('Unable to open command fifo: ' + self.fifo_path + ': ' + str(err))

class VersionCommand(Command):
	def perform(self):
		print('playd 0.1a -- prerelease version.')

def configure_application():

	class GlobalOptions(object): pass
	opts = GlobalOptions()

	home = environ['HOME']
	opts.fifo_path = abspath(join(home, '.' + basename(argv[0])))

	def parse_cmdline(args):
		if not args: return None
		arg = args[0]
		if arg == 'start':
			return parse_start_command(args[1:])
		elif arg == 'stop':
			return parse_stop_command(args[1:])
		elif arg == 'queue':
			return parse_queue_command(args[1:])
		elif arg == 'next':
			return parse_next_command(args[1:])
		else:
			return parse_global_args(args, parse_cmdline)

	def parse_start_command(args):
		def parse_cmd_args(args): parse_global_args(args, parse_cmd_args)
		parse_cmd_args(args)
		return StartCommand(opts.fifo_path)

	def parse_stop_command(args):
		def parse_cmd_args(args): parse_global_args(args, parse_cmd_args)
		parse_cmd_args(args)
		return StopCommand(opts.fifo_path)

	def parse_queue_command(args):
		items = []
		def parse_cmd_args(args):
			if not args: return
			if args[0] and args[0][0] == '-':
				parse_global_args(args, parse_cmd_args)
			else:
				items.append(abspath(args[0]))
				parse_cmd_args(args[1:])
		parse_cmd_args(args)
		return QueueCommand(opts.fifo_path, items)

	def parse_next_command(args):
		def parse_cmd_args(args): parse_global_args(args, parse_cmd_args)
		parse_cmd_args(args)
		return NextCommand(opts.fifo_path)

	def parse_global_args(args, next):
		if not args: return
		arg = args[0]
		if arg == '-v' or arg == '--version':
			opts.version = True
			return next(args[1:])
		else:
			raise CmdLineError("Unexpected argument '" + arg + "'.")

	cmd = parse_cmdline(argv[1:])

	if getattr(opts, 'version', False):
		if not cmd:
			cmd = VersionCommand()
		else:
			raise CmdLineError('--version cannot be used with command.')

	if not cmd:
		raise CmdLineError('No command given.')

	return cmd

def main():
	try:
		cmd = configure_application()

		cmd.perform()

	except FifoMissingError as err:
		argname = basename(argv[0])
		print('The daemon communication FIFO is missing.')
		print('Please make sure that daemon is running (try running "' + argname + ' start").')

	except CmdLineError as err:
		print(err)

if __name__ == '__main__':
	main()
