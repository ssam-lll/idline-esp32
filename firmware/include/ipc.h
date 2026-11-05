#ifndef IDLINE_IPC_H
#define IDLINE_IPC_H

#include <atomic>
#include <cstring>
#include <type_traits>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

namespace idline {

template <typename T>
class Seqlock {
    static_assert(std::is_trivially_copyable<T>::value, "Seqlock payload must be trivially copyable");

private:
    std::atomic<uint32_t> seq_{0};
    T data_{};

public:
    Seqlock() = default;

    void publish(const T& val) {
        uint32_t s = seq_.load(std::memory_order_relaxed);
        seq_.store(s + 1, std::memory_order_release);
        data_ = val;
        seq_.store(s + 2, std::memory_order_release);
    }

    T read() const {
        T result{};
        uint32_t s0, s1;
        do {
            s0 = seq_.load(std::memory_order_acquire);
            while (s0 & 1) {
                taskYIELD();
                s0 = seq_.load(std::memory_order_acquire);
            }
            result = data_;
            s1 = seq_.load(std::memory_order_acquire);
        } while (s0 != s1);
        return result;
    }
};

} // namespace idline

#endif // IDLINE_IPC_H
