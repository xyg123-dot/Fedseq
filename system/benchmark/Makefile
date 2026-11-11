CXX ?= g++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -Wno-unused-function -Wno-sign-compare
SOURCES = edit.cpp filter.cpp hash.cpp partition.cpp
all: system_benchmark native_benchmark
system_benchmark: system_main.cpp rpc_algorithm.cpp rpc_provider.h $(SOURCES) order_bound.h
	$(CXX) $(CXXFLAGS) -DSYSTEM_RPC system_main.cpp $(SOURCES) -pthread -lcrypto -o $@
native_benchmark: system_main.cpp reference_algorithm.cpp $(SOURCES) order_bound.h
	$(CXX) $(CXXFLAGS) system_main.cpp $(SOURCES) -pthread -lcrypto -o $@
test: system_benchmark
	./system_benchmark --crypto-test
clean:
	rm -f system_benchmark native_benchmark
