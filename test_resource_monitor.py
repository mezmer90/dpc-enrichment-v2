"""
Quick test script to verify resource monitoring works correctly.

Run this to ensure psutil and the resource monitor are working before deploying.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.enrichment_v2.utils.resource_monitor import ResourceMonitor
from src.enrichment_v2.scraper.system_circuit_breaker import SystemCircuitBreaker


def test_resource_monitor():
    """Test ResourceMonitor"""
    print("=" * 60)
    print("Testing ResourceMonitor")
    print("=" * 60)

    monitor = ResourceMonitor()

    # Test get_current_usage
    usage = monitor.get_current_usage()
    print("\n[OK] Current Resource Usage:")
    for metric, value in usage.items():
        print(f"   {metric}: {value:.2f}")

    # Test is_healthy
    healthy, reason = monitor.is_healthy()
    print(f"\n[OK] System Healthy: {healthy}")
    print(f"   Reason: {reason}")

    # Test health score
    health_score = monitor.get_health_score()
    print(f"\n[OK] Health Score: {health_score:.2f} (0.0=critical, 1.0=perfect)")

    # Test usage summary
    summary = monitor.get_usage_summary()
    print(f"\n[OK] Usage Summary:")
    print(f"   {summary}")

    # Test critical metrics
    has_critical, critical_metrics = monitor.check_critical_metrics()
    print(f"\n[OK] Critical Metrics: {has_critical}")
    if critical_metrics:
        for metric in critical_metrics:
            print(f"   [WARNING] {metric}")

    print("\n" + "=" * 60)
    print("ResourceMonitor test completed successfully!")
    print("=" * 60)


def test_system_circuit_breaker():
    """Test SystemCircuitBreaker"""
    print("\n" + "=" * 60)
    print("Testing SystemCircuitBreaker")
    print("=" * 60)

    monitor = ResourceMonitor()
    breaker = SystemCircuitBreaker(monitor)

    # Test check_resources_before_task
    can_proceed, reason = breaker.check_resources_before_task()
    print(f"\n[OK] Can Proceed: {can_proceed}")
    print(f"   Reason: {reason}")

    # Test log_resources
    print(f"\n[OK] Logging resources:")
    breaker.log_resources()

    # Test get_state
    state = breaker.get_state()
    print(f"\n[OK] Circuit Breaker State: {state}")

    print("\n" + "=" * 60)
    print("SystemCircuitBreaker test completed successfully!")
    print("=" * 60)


def main():
    """Run all tests"""
    print("\nTesting Resource Monitoring Components")
    print("=" * 60)
    print("This verifies that psutil and resource monitoring work correctly.")
    print("=" * 60 + "\n")

    try:
        test_resource_monitor()
        test_system_circuit_breaker()

        print("\n" + "=" * 60)
        print("[SUCCESS] ALL TESTS PASSED!")
        print("=" * 60)
        print("\nResource monitoring is working correctly.")
        print("You can now deploy with confidence.")
        print("\nNext steps:")
        print("1. Set environment variables in Railway (see RAILWAY_DEPLOYMENT.md)")
        print("2. Push code to Railway")
        print("3. Monitor first 50 practices")
        print("\n")

        return 0

    except Exception as e:
        print("\n" + "=" * 60)
        print("[FAILED] TEST FAILED!")
        print("=" * 60)
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("1. Install psutil: pip install psutil==6.1.1")
        print("2. Install requirements: pip install -r requirements.txt")
        print("\n")

        import traceback
        traceback.print_exc()

        return 1


if __name__ == "__main__":
    sys.exit(main())
