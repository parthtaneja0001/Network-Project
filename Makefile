.PHONY: all test clean

all: bserve bcurl

bserve:
	chmod +x bserve

bcurl:
	chmod +x bcurl

test: all
	python3 test_protocol.py

clean:
	rm -rf __pycache__
