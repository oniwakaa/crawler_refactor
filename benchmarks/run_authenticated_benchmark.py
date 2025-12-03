#!/usr/bin/env python3
"""
Authenticated Benchmark for B2B Lead Generation Pipeline.
Run the 4 queries from the original benchmark with all optimizations enabled.
"""

import asyncio
import sys
from pathlib import Path
import subprocess

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Add the directory containing the benchmark_pipeline.py to the path
sys.path.insert(0, str(Path(__file__).parent))

from benchmark_pipeline import PipelineBenchmark

class AuthenticatedBenchmark(PipelineBenchmark):
    """Run authenticated benchmarks for specific queries."""
    
    async def run_all_benchmarks(self):
        """Run the 4 benchmark queries from requirements."""
        print("\n" + "="*60)
        print("AUTHENTICATED BENCHMARK SUITE")
        print("4 queries from Phase 4 requirements")
        print("="*60)
        
        benchmarks = [
            {"query": "Carlo Bizzaro profile LinkedIn", "max_results": 1, "type": "specific_profile"},
            {"query": "Marketing directors at enterprise software companies Germany", "max_results": 10, "type": "specific_role"},
            {"query": "CTOs at SaaS startups Germany", "max_results": 10, "type": "specific_role"},
            {"query": "Tech startup founders Berlin", "max_results": 10, "type": "broad_search"},
        ]
        
        all_results = []
        
        for benchmark in benchmarks:
            result = await self.run_benchmark(
                query=benchmark["query"],
                max_results=benchmark["max_results"]
            )
            result["query_type"] = benchmark["type"]
            all_results.append(result)
            
            # Small delay between benchmarks
            await asyncio.sleep(2)
        
        # Print summary
        self._print_summary(all_results)
        
        return all_results

async def main():
    """Main benchmark execution."""
    benchmark = AuthenticatedBenchmark()
    await benchmark.run_all_benchmarks()

if __name__ == "__main__":
    asyncio.run(main())
