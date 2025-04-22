.PHONY: test-current test-hw1 count-hw1 upgrade

CURRENT=hw15
PART=all
DIR=..

# Some ideas from https://gist.github.com/sighingnow/deee806603ec9274fd47
ifndef OS
	ifeq ($(OS),Windows_NT)
		OS ?= windows
	else
		UNAME_S := $(shell uname -s)
		ifeq ($(UNAME_S),Linux)
			GLIBC_SUBV := $(shell ldd --version | head -n1 | sed 's/.*2\.\([0-9]*\).*/\1/g')
			ifeq ($(shell test $(VER) -ge 35; echo $$?),0)
				OS ?= linux
			else
				OS ?= linux
			endif
		endif
		ifeq ($(UNAME_S),Darwin)
			OS ?= macos
		endif
	endif
endif

test-current: test-$(CURRENT)
count-current: count-$(CURRENT)

count-hw1:
	@ sh hw1/test-part $(DIR) count

count-hw%:
	@ python3 grader.py count --hw $*


test-hw1: jplc
	@ sh hw1/test-part $(DIR) $(PART)

test-hw2:
	@ python3 grader.py test --hw 2 --dir $(DIR) --part $(PART)

test-hw3:
	@ python3 grader.py test --hw 3 --dir $(DIR) --part $(PART)

test-hw4:
	@ python3 grader.py test --hw 4 --dir $(DIR) --part $(PART)

test-hw5:
	@ python3 grader.py test --hw 5 --dir $(DIR) --part $(PART)

test-hw6:
	@ python3 grader.py test --hw 6 --dir $(DIR) --part $(PART)

test-hw7:
	@ python3 grader.py test --hw 7 --dir $(DIR) --part $(PART)

test-hw8:
	@ python3 grader.py test --hw 8 --dir $(DIR) --part $(PART)

test-hw9:
	@ python3 grader.py test --hw 9 --dir $(DIR) --part $(PART)

test-hw89:
	@ python3 grader.py test --hw 89 --dir $(DIR) --part $(PART)

test-hw10:
	@ python3 grader.py test --hw 10 --dir $(DIR) --part $(PART)

test-hw11:
	@ python3 grader.py test --hw 11 --dir $(DIR) --part $(PART)

test-hw1011:
	@ python3 grader.py test --hw 1011 --dir $(DIR) --part $(PART)

test-hw12:
	@ python3 grader.py test --hw 12 --dir $(DIR) --part $(PART)

test-hw13:
	@ python3 grader.py test --hw 13 --dir $(DIR) --part $(PART)

# ben: completely useless??
test-hw%:
	@ python3 grader.py run --hw $*

test-hw14:
	@ python3 grader.py test --hw 14 --dir $(DIR) --part $(PART)

test-hw15:
	@ python3 grader.py test --hw 15 --dir $(DIR) --part $(PART)

jplc:
	curl -L 'https://github.com/utah-cs4470-sp25/class/releases/latest/download/jplc-$(OS)' -o ./jplc
	chmod +x jplc

print-os:
	@ echo $(OS)

upgrade:
	git pull origin main
	$(MAKE) -B jplc OS=$(OS)
