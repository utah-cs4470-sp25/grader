.PHONY: test-current test-hw1 count-hw1 upgrade

CURRENT=hw2
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

count-hw14:
	@ sh hw14/test-part $(DIR) count


test-hw1: jplc
	@ sh hw1/test-part $(DIR) $(PART)

test-hw2:
	@ python3 grader.py test --hw 2 --dir $(DIR) --part $(PART)

test-hw3:
	@ python3 grader.py test --hw 3 --dir $(DIR) --part $(PART)

test-hw%:
	@ python3 grader.py run --hw $*

test-hw14:
	@ sh hw14/test-part $(DIR) $(PART)

jplc:
	curl -L 'https://github.com/utah-cs4470-sp25/class/releases/latest/download/jplc-$(OS)' -o ./jplc
	chmod +x jplc

print-os:
	@ echo $(OS)

upgrade:
	git pull origin main
	$(MAKE) -B jplc OS=$(OS)
