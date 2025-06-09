
import os
import sys
import time
import shlex
import argparse
import subprocess
import threading
import re

if sys.version_info >= (3, 7):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

class Tail(object):
    def __init__(self, tailed_file):
        self.check_file_validity(tailed_file)
        self.tailed_file = tailed_file
        self.callback = sys.stdout.write

    def follow(self, stop_event, s=1):
        with open(self.tailed_file, 'r', encoding='utf-8', errors='replace') as file_:
            # Go to the end of file
            file_.seek(0,2)
            while not stop_event.is_set():
                curr_position = file_.tell()
                line = file_.readline()
                if not line:
                    file_.seek(curr_position)
                    time.sleep(s)
                else:
                    self.callback(line)

    def register_callback(self, func):
        self.callback = func

    def check_file_validity(self, file_):
        if not os.access(file_, os.F_OK):
            raise TailError("File '%s' does not exist" % (file_))
        if not os.access(file_, os.R_OK):
            raise TailError("File '%s' not readable" % (file_))
        if os.path.isdir(file_):
            raise TailError("File '%s' is a directory" % (file_))

class TailError(Exception):
    def __init__(self, msg):
        self.message = msg
    def __str__(self):
        return self.message

def log_reader(t):
    print(t, end='')

def tail(stop_event, filename, timeout=6):
    _c = 0
    _p = 0.5
    while not os.path.exists(filename):
        if timeout < _c*_p:
            break
        _c += 1
        print("Wait `%s`..." % filename)
        time.sleep(_p)

    t = Tail(filename)
    t.register_callback(log_reader)
    t.follow(stop_event)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-logFile")
    parsed_args, unknown_args = parser.parse_known_args()
    # print(parsed_args, unknown_args)
    cmd = " ".join([shlex.quote(arg).replace("'", '"') if ' ' in arg else arg for arg in sys.argv[1:]])
    args = shlex.split(cmd)
    print(cmd)

    stop_event = threading.Event()
    if os.path.exists( parsed_args.logFile):
        os.remove( parsed_args.logFile)
    th = threading.Thread(target=tail, args=(stop_event, parsed_args.logFile, ))
    th.start()

    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='replace')
    try:
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(f"[Unity Process] " + output.strip())
        stderr_output = process.stderr.read()
        if stderr_output:
            print(f"[Unity Process] Error: {stderr_output.strip()}")
    except KeyboardInterrupt:
        print("[Unity Process] interrupted by user")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

        return_code = process.returncode
        print(f"[Unity Process] return code: {return_code}")

    stop_event.set()
    th.join()
    with open(parsed_args.logFile, 'r', encoding='utf-8', errors='replace') as file:
        text = file.read()
        if re.search('DisplayProgressNotification: Build Successful', text):
            sys.exit(0)

        exit_codes = re.findall(r'ExitCode:\s*(\d+)', text)
        exit_codes = list(map(int, exit_codes))
        if exit_codes and all(code == 0 for code in exit_codes):
            print('All exit codes are 0')
            sys.exit(0)
    sys.exit(-1)
