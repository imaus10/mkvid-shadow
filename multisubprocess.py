from multiprocessing import Pipe, Pool
import subprocess
import sys


def pipe_subprocess_output(cmd, output_pipe, last_stage=False):
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    is_running = True
    while is_running:
        is_running = process.poll() is None
        line = process.stdout.readline().strip()
        if line:
            output_pipe.send(line)
    # signal the start of a new stage for this process
    if not last_stage:
        output_pipe.send('NEWLINE')


def print_process_progress(outputs, num_clear_lines=0):
    if num_clear_lines:
        num_clear_lines += len(outputs)
        print(f'\033[{num_clear_lines}A', end='')
        print('\033[J', end='')
    for i, stages in enumerate(outputs):
        print(f'Process {i}:')
        for line in stages:
            print(line)


def subprocess_pool(func, args):
    # append the sender end of the pipes to the args,
    # so that each of the subprocesses
    # can report their progress in parallel
    # (`send_pipe` is passed along into `pipe_subprocess_output` above)
    recv_pipes, send_pipes = zip(*[ Pipe(duplex=False) for _ in args ])
    args = [ (*a, send_pipe) for a, send_pipe in zip(args, send_pipes) ]
    with Pool() as party:
        processes = party.starmap_async(func, args, error_callback=print)
        last_outputs = [ ['...'] for _ in recv_pipes ]
        print_process_progress(last_outputs)
        while not processes.ready():
            num_clear_lines = 0
            for i, pipe in enumerate(recv_pipes):
                if pipe.poll():
                    line = pipe.recv()
                    # only get the number of lines to clear
                    # on the first time per loop,
                    # in case multiple chunks send "DONE"
                    if not num_clear_lines:
                        num_clear_lines = sum(map(lambda out: len(out), last_outputs))
                    # each parallel process has multiple steps.
                    # make a new line for the new step
                    if line == 'NEWLINE':
                        last_outputs[i].append('...')
                    else:
                        last_outputs[i][-1] = line
            if num_clear_lines:
                print_process_progress(last_outputs, num_clear_lines)
        if not processes.successful():
            sys.exit()
