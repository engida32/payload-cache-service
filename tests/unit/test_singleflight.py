import threading
from time import sleep

from payload_cache.services.singleflight import SingleFlight


def test_concurrent_callers_run_the_function_once():
    flight = SingleFlight()
    calls = []
    results = []

    def work():
        calls.append(1)
        sleep(0.05)
        return "value"

    def call():
        results.append(flight.run("key", work)[0])

    threads = [threading.Thread(target=call) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(calls) == 1
    assert results == ["value"] * 8


def test_only_one_caller_is_the_leader():
    flight = SingleFlight()
    leaders = []

    def slow():
        sleep(0.05)
        return "value"

    def call():
        leaders.append(flight.run("key", slow)[1])

    threads = [threading.Thread(target=call) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert leaders.count(True) == 1


def test_errors_reach_every_waiter_and_do_not_poison_the_key():
    flight = SingleFlight()
    errors = []

    def boom():
        sleep(0.02)
        raise RuntimeError("upstream down")

    def call():
        try:
            flight.run("key", boom)
        except RuntimeError as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=call) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == ["upstream down"] * 3
    assert flight.run("key", lambda: "recovered")[0] == "recovered"


def test_keys_do_not_block_each_other():
    flight = SingleFlight()
    release = threading.Event()
    done = threading.Event()

    def slow():
        release.wait(2)
        return "slow"

    def fast():
        done.set()
        return "fast"

    thread = threading.Thread(target=lambda: flight.run("slow", slow))
    thread.start()
    assert flight.run("fast", fast)[0] == "fast"
    assert done.is_set()
    release.set()
    thread.join()
