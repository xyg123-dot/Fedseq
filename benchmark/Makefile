CXX ?= g++
CXXFLAGS ?= -std=c++17 -O3 -Wall -Wextra
LDLIBS = -lcrypto
SOURCES = fedknn_benchmark.cpp edit.cpp filter.cpp hash.cpp partition.cpp
HEADERS = minsearch.h edit.h filter.h hash.h partition.h match.h timerec.h order_bound.h

all: fedknn_benchmark
fedknn_benchmark: $(SOURCES) $(HEADERS)
	$(CXX) $(CXXFLAGS) $(SOURCES) -o $@ $(LDLIBS)
test: fedknn_benchmark
	./fedknn_benchmark --self-test
sanitize:
	$(CXX) -std=c++17 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer $(SOURCES) -o fedknn_sanitize $(LDLIBS)
	ASAN_OPTIONS=detect_leaks=0 ./fedknn_sanitize --self-test
.PHONY: all test sanitize

test_privacy: test_privacy.cpp $(SOURCES) $(HEADERS)
	$(CXX) $(CXXFLAGS) -Wno-unused-function test_privacy.cpp edit.cpp filter.cpp hash.cpp partition.cpp -o $@ $(LDLIBS)
privacy_test: test_privacy
	./test_privacy

replay_accuracy: replay_accuracy.cpp $(SOURCES) $(HEADERS)
	$(CXX) $(CXXFLAGS) -Wno-unused-function replay_accuracy.cpp edit.cpp filter.cpp hash.cpp partition.cpp -o $@ $(LDLIBS)
