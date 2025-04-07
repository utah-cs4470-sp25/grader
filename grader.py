#!/usr/bin/env python3

from typing import Optional, Tuple
from dataclasses import dataclass
import traceback
import shlex
import difflib
from normalize_asm import ppasm, ppc, commentasm
from ppsexp import ppsexp, unpp
from pathlib import Path
import subprocess
import concurrent.futures as futures
import argparse, sys, os
import shutil
import re

DIR=os.environ.get("DIR", "~/jpl/pavpan/")
TIMEOUT=60 # Seconds

class ParseSuccessError(Exception): pass
class CompilerFailed(Exception): pass
class CompilerTimeout(Exception): pass
class CompilerInvalid(Exception): pass

def parse_success(out : str) -> Tuple[bool, str]:
    parts = out.strip().rsplit("\n", 1)
    if len(parts) > 1:
        main_body, last_line = parts
    else:
        main_body, last_line = "", parts[0]
    last_line = last_line.casefold()
    has_success = last_line.count("Compilation succeeded".casefold())
    has_failure = last_line.count("Compilation failed".casefold())
    if has_success and has_failure:
        raise ParseSuccessError("Found both 'Compilation succeeded' and 'Compilation failed'")
    elif has_success > 1:
        raise ParseSuccessError("Found 'Compilation succeeded' more than once")
    elif has_failure > 1:
        raise ParseSuccessError("Found 'Compilation failed' more than once")
    elif has_success == 0 and has_failure == 0:
        if "Compilation succeeded".casefold() in main_body.casefold():
            raise ParseSuccessError("'Compilation succeeded' message not last line of output")
        elif "Compilation failed".casefold() in main_body.casefold():
            raise ParseSuccessError("'Compilation failed' message not last line of output")
        else:
            raise ParseSuccessError("Could not find 'Compilation succeeded' or 'Compilation failed'")
    else:
        return has_success > has_failure, main_body

def run_student(flags, in_file, require=None):
    try:
        res = subprocess.run([
            "make",
            "--silent", # Don't print commands as they are run
            "--no-print-directory", # Don't print change directory message
            "-C", DIR,
            "run",
            "FLAGS=" + flags,
            "TEST=" + str(in_file.resolve()),
        ], capture_output=True, timeout=TIMEOUT, text=True)
    except subprocess.TimeoutExpired as e:
        raise CompilerTimeout(e)
    except subprocess.CalledProcessError as e:
        raise CompilerFailed(e)
    else:
        try:
            success, out = parse_success(res.stdout)
        except ParseSuccessError as e:
            raise CompilerInvalid(str(e), res.stdout, res.stderr)
        if require is not None and success != require:
            raise CompilerInvalid(f"File should {'' if require else 'NOT '}have been accepted", out, res.stderr)
        return success, out, res.stderr

def run_compiler(flags, in_file):
    res = subprocess.run(["./jplc"] + shlex.split(flags) + [str(in_file.resolve())],
                         capture_output=True, timeout=TIMEOUT, text=True)
    try:
        success, out = parse_success(res.stdout)
    except ParseSuccessError as e:
        print(e)
        print(res.stdout)
        raise
    if not success:
        raise ValueError(f"File {in_file} should have been accepted with {flags}")
    return out

@dataclass
class FileSpec:
    in_file : Path
    flags : str

    def matches(self, name):
        return name == "all" or self.in_file.name.startswith(name)

    def index(self):
        idx = self.in_file.name
        if self.in_file.name.endswith(".jpl"):
            idx = self.in_file.name.removesuffix(".jpl")
        if idx.isdigit():
            idx = f"{idx:0>8}"
        return idx

    def run(self):
        raise NotImplementedError

    def regen(self):
        raise NotImplementedError

@dataclass
class ValidSpec(FileSpec):
    def run(self):
        run_student(self.flags, self.in_file, require=True)

    def regen(self):
        pass

@dataclass
class InvalidSpec(FileSpec):
    def run(self):
        run_student(self.flags, self.in_file, require=False)

    def regen(self):
        pass

def diff(fromtext, totext, fromfile=None, tofile=None, fromcomments=None, tocomments=None):
    frommap = fromcomments or {}
    tomap = tocomments or {}
    diff_lines = list(difflib.context_diff(
        fromtext, totext, lineterm="", fromfile=fromfile, tofile=tofile))
    if diff_lines:
        count = len([line for line in diff_lines if line.startswith("- ") or line.startswith("+ ") or line.startswith("! ")])
        raise CompilerInvalid(f"{count} lines differ", "\n".join(readd_comments(diff_lines, frommap, tomap)), None)

FROM_RE = re.compile(r"\*\*\* ([0-9]+),[0-9]+ \*\*\*\*")
TO_RE = re.compile(r"--- ([0-9]+),[0-9]+ ----")

def readd_comments(diff_lines, from_map, to_map):
    lns = []
    to_linenum = None
    from_linenum = None
    for ln in diff_lines:
        if ln.startswith("*****") or ln.startswith("===="):
            # reset
            from_linenum = None
            to_linenum = None
            lns.append(ln)
            continue
        from_m = re.match(FROM_RE, ln)
        if from_m:
            # parse current line num
            to_linenum = None
            from_linenum = int(from_m.group(1))
            lns.append(ln)
            continue
        to_m = re.match(TO_RE, ln)
        if to_m:
            from_linenum = None
            to_linenum = int(to_m.group(1))
            lns.append(ln)
            continue
        if from_linenum:
            # add comment, if one exists
            lns.append(ln + from_map.get(from_linenum, ""))
            from_linenum += 1
            continue
        if to_linenum:
            # ditto
            lns.append(ln + to_map.get(to_linenum, ""))
            to_linenum += 1
            continue
        if True:
            # boring line
            lns.append(ln)
            continue
    return lns

@dataclass
class DiffSpec(FileSpec):
    expected_file : Path
    normalize : None
    comment_map : None

    def __init__(self, in_file, flags, normalize=None, comment=None):
        self.in_file = in_file
        self.flags = flags
        self.expected_file = in_file.parent / (in_file.name + ".expected")
        self.normalize = normalize
        self.comment_map = comment

    def run(self):
        assert self.expected_file.exists(), \
            f"Expected output for {self.expected_file.name} not found"
        with self.expected_file.open() as f:
            expected = f.read()
        success, out, err = run_student(self.flags, self.in_file, require=True)
        expected = expected.strip().split("\n")
        out = out.strip().split("\n")
        lcmap = {}
        exp_cmap = None
        out_cmap = None
        if self.normalize:
            if self.comment_map:
                exp_cmap = dict(self.comment_map(expected))
                out_cmap = dict(self.comment_map(out))
            expected = list(self.normalize(expected))
            out = list(self.normalize(out))
        diff(expected, out, fromfile=self.expected_file.name, tofile="Your compiler", fromcomments=exp_cmap, tocomments=out_cmap)

    def regen(self):
        out = run_compiler(self.flags, self.in_file)
        with self.expected_file.open("wt") as f:
            f.write(out)

@dataclass
class OptSpec(FileSpec):
    expected_O0 : Path
    expected_O1 : Path

    def __init__(self, in_file, flags):
        self.in_file = in_file
        self.flags = flags
        self.expected_O0 = in_file.parent / (in_file.name + ".expected")
        self.expected_O1 = in_file.parent / (in_file.name + ".expected.opt")

    def run(self):
        assert self.expected_O0.exists(), \
            f"Expected output for {self.expected_O0.name} not found"
        with self.expected_O0.open() as f:
            expected = f.read()
        success, out, err = run_student("-s", self.in_file, require=True)
        expected = list(ppasm(expected.strip().split("\n")))
        out = list(ppasm(out.strip().split("\n")))
        diff(expected, out, fromfile=self.expected_O0.name, tofile="Your compiler")

        assert self.expected_O1.exists(), \
            f"Expected output for {self.expected_O1.name} not found"
        with self.expected_O1.open() as f:
            expected = f.read()
        success, out, err = run_student(f"-s {self.flags}", self.in_file, require=True)
        expected = list(ppasm(expected.strip().split("\n")))
        out = list(ppasm(out.strip().split("\n")))
        diff(expected, out, fromfile=self.expected_O1.name, tofile="Your compiler")

    def regen(self):
        self.expected_O0.open("wt").write(run_compiler("-s", self.in_file))
        self.expected_O1.open("wt").write(run_compiler(f"-s {self.flags}", self.in_file))

@dataclass
class RunSpec(FileSpec):
    def run(self):
        success, out, err = run_student(self.flags, self.in_file)
        msg = "was successful" if success else "failed"
        raise CompilerInvalid(f"Compilation {msg}", out, err)

def print_fancy(name, out):
    if not out: return
    if isinstance(out, bytes): out = out.decode("latin1")
    print(f"======= {name}: =======")
    print(out)
    print()
    print(f"=======================")

def makespec(T, path, *args, **kwargs):
    for f in sorted(path.iterdir(), key=lambda f: f.name):
        if f.name.endswith(".jpl"):
            yield T(f, *args, **kwargs)

def regen_all(filespecs):
    failures = 0
    for filespec in filespecs:
        print(filespec.in_file.name, "...", flush=True, end=" ")
        try:
            filespec.regen()
        except CompilerInvalid as e:
            failures += 1
            print("error")
            print(str(e.args[0]))
            print(e.args[1])
            break
        except Exception:
            failures += 1
            print("error")
            raise
        else:
            print("done")
    return failures

def test_one(filespec : FileSpec) -> Tuple[str, str, Optional[str], Optional[str]]:
    try:
        filespec.run()
    except CompilerTimeout as e:
        e = e.args[0]
        msg = f"{filespec.in_file.name}: Timeout after {e.timeout} seconds"
        return "T", msg, e.stdout, e.stderr
    except CompilerFailed as e:
        e = e.args[0]
        msg = f"{filespec.in_file.name}: Process returned bad error code {e.returncode}"
        return "F", msg, e.stdout, e.stderr
    except CompilerInvalid as e:
        msg, out, err = e.args
        msg = f"{filespec.in_file.name}: {msg}"
        return "W", msg, out, err
    else:
        return ".", "", None, None

def test_all(name, filespecs, threads=None):
    total = 0
    failure = 0
    total_since = len(name) + 1
    filespecs = sorted(filespecs, key=FileSpec.index)
    outputs = []
    print(f"{name} ", end="", flush=True)
    if threads is None:
        domap = map
    else:
        pool = futures.ThreadPoolExecutor(max_workers=threads)
        domap = pool.map
    for status, msg, out, err in domap(test_one, filespecs):
        total += 1
        total_since += 1
        print(status, end="", flush=True)
        if status != ".":
            print()
            print(msg)
            print_fancy("Standard Out", out)
            print_fancy("Standard Error", err)
            total_since = 0
            failure += 1
        if total_since > 71:
            total_since = 0
            print()
    print()
    print(f"Passed {total - failure}/{total} = {(1 - failure/total)*100:.1f}% tests")
    if threads:
        pool.shutdown()
    return failure

class NullPart:
    def __init__(self, spec, path, *args, **kwargs):
        self.spec = spec
        self.path = HERE / path
        self.args = args
        self.kwargs = kwargs

    def unpack(self):
        pass

    def all(self):
        return makespec(self.spec, self.path, *self.args, **self.kwargs)

class ManualPart:
    def __init__(self, spec, file, path, *args, **kwargs):
        self.spec = spec
        self.file = HERE / file
        self.path = HERE / path
        self.args = args
        self.kwargs = kwargs

    def unpack(self):
        print("Unpacking", self.file.name, end=" ", flush=True)
        with self.file.open("rt") as f:
            tests = f.read().split("\n\n")
        for i, part in enumerate(tests):
            print(".", end="", flush=True)
            with open(self.path / f"{i+1:03}.jpl", "w") as f:
                f.write(part + "\n")
        print()

    def all(self):
        return makespec(self.spec, self.path, *self.args, **self.kwargs)

class FuzzerPart:
    def __init__(self, spec, path, number, subset, seed, *args, fuzz=False, **kwargs):
        self.spec = spec
        self.path = HERE / path
        self.number = number
        self.subset = subset
        self.seed = seed
        self.fuzz = fuzz
        self.args = args
        self.kwargs = kwargs

    def unpack(self):
        res = subprocess.run([
            "python3", DIR + "src/fuzzer.py",
            str(self.number),
            "--seed", str(self.seed),
            "--subset", str(self.subset),
            "--out-dir", str(self.path),
        ] + (["--fuzz"] if self.fuzz else []), check=True, stdout=sys.stdout, stderr=sys.stderr)

    def all(self):
        return makespec(self.spec, path, *self.args, **kwargs)

HERE = Path(__file__).parent.resolve()

CURRENT_HW = "3"

HWS = {
   "2": {
       "1": NullPart(DiffSpec, "hw2/lexer-tests1/", "-l"),
       "2": NullPart(ValidSpec, "hw2/lexer-tests2/", "-l"),
       "3": NullPart(InvalidSpec, "hw2/lexer-tests3/", "-l"),
   },
   "3": {
       "1": NullPart(DiffSpec, "hw3/ok/", "-p", normalize=unpp), # TODO ppsexp
       "2": NullPart(DiffSpec, "hw3/ok-fuzzer/", "-p", normalize=unpp),
       "3": NullPart(InvalidSpec, "hw3/fail-fuzzer1/", "-p"),
       "4": NullPart(InvalidSpec, "hw3/fail-fuzzer2/", "-p"),
       "5": NullPart(InvalidSpec, "hw3/fail-fuzzer3/", "-p"),
   },
   "4": {
       "1": ManualPart(DiffSpec, "hw4/ok.jpl", "hw4/ok/", "-p", normalize=unpp),
       "2": NullPart(DiffSpec, "hw4/ok-fuzzer/", "-p", normalize=unpp),
       "3": NullPart(InvalidSpec, "hw4/fail-fuzzer1/", "-p"),
       "4": NullPart(InvalidSpec, "hw4/fail-fuzzer2/", "-p"),
       "5": NullPart(InvalidSpec, "hw4/fail-fuzzer3/", "-p"),
   },
   "5": {
       "1": ManualPart(DiffSpec, "hw5/ok.jpl", "hw5/ok/", "-p", normalize=unpp),
       "2": NullPart(DiffSpec, "hw5/ok-fuzzer/", "-p", normalize=unpp),
       "3": NullPart(InvalidSpec, "hw5/fail-fuzzer1/", "-p"),
       "4": NullPart(InvalidSpec, "hw5/fail-fuzzer2/", "-p"),
       "5": NullPart(InvalidSpec, "hw5/fail-fuzzer3/", "-p"),
   },
   "6": {
       "1": ManualPart(DiffSpec, "hw6/ok.jpl", "hw6/ok/", "-t", normalize=unpp),
       "2": NullPart(DiffSpec, "hw6/ok-fuzzer/", "-t", normalize=unpp),
       "3": NullPart(InvalidSpec, "hw6/fail-fuzzer1/", "-t"),
       "4": NullPart(InvalidSpec, "hw6/fail-fuzzer2/", "-t"),
       "5": NullPart(InvalidSpec, "hw6/fail-fuzzer3/", "-t"),
   },
   "7": {
       "1": ManualPart(DiffSpec, "hw7/ok.jpl", "hw7/ok/", "-t", normalize=unpp),
       "2": ManualPart(InvalidSpec, "hw7/fail.jpl", "hw7/fail/", "-t"),
       "3": NullPart(DiffSpec, "hw7/ok-fuzzer/", "-t", normalize=unpp),
       "4": NullPart(InvalidSpec, "hw7/fail-fuzzer/", "-t"),
   },
   "8": {
       "1": NullPart(DiffSpec, "hw8/ok/", "-i", normalize=ppc),
       "2": NullPart(DiffSpec, "hw8/ok-fuzzer/", "-i", normalize=ppc),
   },
   "9": {
       "1": NullPart(DiffSpec, "hw9/ok/", "-i", normalize=ppc),
       "2": NullPart(DiffSpec, "hw9/ok-fuzzer/", "-i", normalize=ppc),
   },
   "89": { # lol delete this after sp25
       "1": NullPart(DiffSpec, "hw8/ok/", "-i", normalize=ppc),
       "2": NullPart(DiffSpec, "hw8/ok-fuzzer/", "-i", normalize=ppc),
       "3": NullPart(DiffSpec, "hw9/ok/", "-i", normalize=ppc),
       "4": NullPart(DiffSpec, "hw9/ok-fuzzer/", "-i", normalize=ppc),
   },


   "10": {
       "1": NullPart(DiffSpec, "hw10/ok/", "-s", normalize=ppasm, comment=commentasm),
       "2": NullPart(DiffSpec, "hw10/ok-fuzzer1/", "-s", normalize=ppasm, comment=commentasm),
       "3": NullPart(DiffSpec, "hw10/ok-fuzzer2/", "-s", normalize=ppasm, comment=commentasm),
   },
   "11": {
       "1": NullPart(DiffSpec, "hw11/ok1/", "-s", normalize=ppasm, comment=commentasm),
       "2": NullPart(DiffSpec, "hw11/ok2/", "-s", normalize=ppasm, comment=commentasm),
       "3": NullPart(DiffSpec, "hw11/ok3/", "-s", normalize=ppasm, comment=commentasm),
       "4": NullPart(DiffSpec, "hw11/ok-fuzzer1/", "-s", normalize=ppasm, comment=commentasm),
       "5": NullPart(DiffSpec, "hw11/ok-fuzzer2/", "-s", normalize=ppasm, comment=commentasm),
   },
   "1011": {
       "1": NullPart(DiffSpec, "hw10/ok/", "-s", normalize=ppasm, comment=commentasm),
       "2": NullPart(DiffSpec, "hw10/ok-fuzzer12/", "-s", normalize=ppasm, comment=commentasm),
       ##"2": NullPart(DiffSpec, "hw10/ok-fuzzer1/", "-s", normalize=ppasm, comment=commentasm),
       ## "3": NullPart(DiffSpec, "hw10/ok-fuzzer2/", "-s", normalize=ppasm, comment=commentasm),
       "3": NullPart(DiffSpec, "hw11/ok1/", "-s", normalize=ppasm, comment=commentasm),
       "4": NullPart(DiffSpec, "hw11/ok2/", "-s", normalize=ppasm, comment=commentasm),
       "5": NullPart(DiffSpec, "hw11/ok3/", "-s", normalize=ppasm, comment=commentasm),
       "6": NullPart(DiffSpec, "hw11/ok-fuzzer12/", "-s", normalize=ppasm, comment=commentasm),
       ##"7": NullPart(DiffSpec, "hw11/ok-fuzzer1/", "-s", normalize=ppasm, comment=commentasm),
       ##"8": NullPart(DiffSpec, "hw11/ok-fuzzer2/", "-s", normalize=ppasm, comment=commentasm),
   },


   "12": {
       "1": NullPart(DiffSpec, "hw12/if/", "-s", normalize=ppasm, comment=commentasm),
       "2": NullPart(DiffSpec, "hw12/index/", "-s", normalize=ppasm, comment=commentasm),
       "3": NullPart(DiffSpec, "hw12/sum/", "-s", normalize=ppasm, comment=commentasm),
       "4": NullPart(DiffSpec, "hw12/array/", "-s", normalize=ppasm, comment=commentasm),
       "5": NullPart(DiffSpec, "hw12/args/", "-s", normalize=ppasm, comment=commentasm),
       "6": NullPart(DiffSpec, "hw12/fuzzer/", "-s", normalize=ppasm, comment=commentasm),
   },
   "13": {
       "1": NullPart(OptSpec, "hw13/ok1/", "-O1"),
       "2": NullPart(OptSpec, "hw13/ok2/", "-O1"),
       "3": NullPart(OptSpec, "hw13/ok3/", "-O1"),
       "4": NullPart(OptSpec, "hw13/ok4/", "-O1"),
       "5": NullPart(OptSpec, "hw13/ok5/", "-O1"),
   },
   "14": {
       "1": ManualPart(OptSpec, "hw14/ok1.jpl", "hw14/ok1/", "-O2"),
       "2": ManualPart(OptSpec, "hw14/ok2.jpl", "hw14/ok2/", "-O2"),
       "3": NullPart(OptSpec, "hw14/ok-fuzzer/", "-O2"),
   },
}

def get_keys(d, keys, name, current=None):
    if keys == "all":
        return d
    elif keys == "current" and current is not None:
        return get_keys(d, current, name)
    elif "," in keys:
        out = dict()
        for pat in keys.split(","):
            out.update(get_keys(d, pat, name))
        return out
    elif keys in d:
        return { keys: d[keys] }
    else:
        assert False, f"Unknown {name} {keys}, only have these:\n  {', '.join(d.keys())}"

def main(args):
    failures = 0
    assert args.tool in ["test", "count", "regen", "run"], \
        f"Unknown tool {args.tool}; only have these:\n  test, count, regen, run"

    homeworks = get_keys(HWS, args.hw, "homework")
    if args.tool == "count":
        assert len(homeworks) == 1, "Cannot 'count' more than one homework at a time"

    for hwname, homework in homeworks.items():
        if hwname == "1":
            assert shutil.which("compare"), "Please install the `compare` tool to test this homework locally"
        else:
            assert shutil.which("make"), "Please install `make` to test this homework locally"

        parts = get_keys(homework, args.part, f"hw{hwname} part")
        if args.tool == "count":
            return print(len([k for k in parts.keys() if k.isdigit()]))

        for partname, part in parts.items():
            if args.tool == "regen":
                part.unpack()

            tests = [test for test in part.all() if test.matches(args.test)]
            assert tests, f"Unknown test {args.test} in hw{hwname} part {partname}"

            name = f"Homework {hwname} part {partname}"
            if args.tool == "test":
                failures += test_all(name, tests, threads=args.threads)
            elif args.tool == "regen":
                failures += regen_all(tests)
            elif args.tool == "run":
                new_tests = [RunSpec(test.in_file, test.flags) for test in tests]
                failures += test_all(name, new_tests, threads=args.threads)
    sys.exit(failures)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test and grade CS 4470 assignments")
    parser.add_argument("tool", type=str,
                        help="What to do: test, count, regen, run")
    parser.add_argument("--hw", type=str, default="current",
                        help="Which homework assignment to test")
    parser.add_argument("--dir", type=str, default="..",
                        help="The compiler directory")
    parser.add_argument("--part", type=str, default="all",
                        help="Which phase assignment to test")
    parser.add_argument("--test", type=str, default="all",
                        help="Which specific test to run")
    parser.add_argument("--threads", type=int, default=None,
                        help="When passed, run the compiler in parallel for more speed")
    args = parser.parse_args()
    DIR = args.dir
    try:
        main(args)
    except KeyboardInterrupt:
        print("interrupted")
        sys.exit(128)
    except AssertionError as e:
        print(f"Error: {e}")
        sys.exit(129)
    except Exception as e:
        total_since = 0
        print("X")
        print(f"The auto-grader encountered a fatal error")
        print("Please report this to the instructors")
        print("======= Traceback: =======")
        traceback.print_exc()
        sys.exit(130)
