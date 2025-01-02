CS 4470 Compilers Auto-grader
=============================

Public auto-grader for CS 4470 Compilers.

Grader will **automatically** run any time you push to your repo,
via GitHub Actions.

You may also download this repo to run it anytime.


Structure of the auto-grader
----------------------------

The auto-grader contains one folder for each homework assignment,
named `hw1/`, `hw2/`, and so on. Each folder contains scripts as well as
test files and directories.

Each homework assignment consists of multiple *parts*---between 1 and
6 of them. Each part is graded separately and has a separate weight
given in each assignment description. They are run separately. A part
typically consists of a number of individual tests (usually about a
hundred, though it varies). Your score for each part is typically the
number of tests passed.

Pull often to keep your auto-grader up to date. In certain cases the
instructors will fix bugs, add or remove tests, or make other changes to the
auto-grader. If you are using an out-of-date auto-grader, you may waste time
fixing bugs or implementing features that you are not supposed to handle.

Grades are determined by the auto-grader on GitHub when you push to
your compiler repository. If autograding works on your machine but not on
GitHub, **you will not receive credit**.

TLDR, push to GitHub early and often to check your progress.


Running the auto-grader
-----------------------

Prerequisites:

* download this grader repo
* download your compiler repo
* know the absolute paths to both repos

Dependencies:

* Unix shell (we have tested with Dash and Bash)
* Make (GNU Make)
* `grep`, `sed`, and possibly other standard Unix tools
* GCC (or compatible compiler, tested only GCC)
* NASM (or compatible assembler, tested only NASM)
* Imagemagick tools (for hw1)

Run the auto-grader like so:

    make -C /autograder/repo test-current DIR=/compiler/repo PART=X

Here both paths **must be absolute paths**.

Here the `X` is `PART=X` is a number from 1 to however many parts your
assignment has. If you are unsure, check the assignment description.

The `test-current` rule runs the current homework, as of whenever you
last pulled from the grader repository. Additionally, you can run a
specific homework assignment like so:

    make -C /autograder/repo test-hw3 DIR=/compiler/repo PART=X

Here you can choose any (released) homework assignment instead of
`hw3`.

If you see any unexpected error messages, contact the instructors.


Troubleshooting
---------------

On Linux, you might get an error about the required GLIBC version. You
may be able to fix it by running this command:

    make -C /autograder/repo -B jplc OS=linux-old

This downloads a special version of the JPL compiler made for older
(2018-era) Linux distributions.


