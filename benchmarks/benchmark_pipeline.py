#!/usr/bin/env python3
"""
Benchmark script for B2B Lead Generation Pipeline.
Measures performance across different query types and generates comprehensive reports.
"""

import asyncio
import time
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.b2b_lead_pipeline import B2BLeadPipeline, PipelineConfig
from dotenv import load_dotenv

class PipelineBenchmark:
    """Benchmark suite for lead generation pipeline."""
    
    def __init__(self):
        self.results_dir = Path("benchmarks/results")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        load_dotenv()
        
    async def run_benchmark(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """Run pipeline and collect metrics."""
        print(f"\n{'='*60}")
        print(f"Benchmarking: {query}")
        print(f"Max Results: {max_results}")
        print(f"{'='*60}")
        
        config = PipelineConfig(
            query=query,
            max_results=max_results,
            settings_path="config/settings.yaml"
        )
        
        start_time = time.time()
        phase_times = {}
        
        try:
            async with B2BLeadPipeline(config) as pipeline:
                # Track phase times (would need to instrument pipeline for detailed metrics)
                lead_batch = await pipeline.run_pipeline()
                
                total_time = time.time() - start_time
                
                # Calculate metrics
                metrics = {
                    "query": query,
                    "max_results": max_results,
                    "total_execution_time": total_time,
                    "total_leads_found": len(lead_batch.leads),
                    "throughput_leads_per_second": len(lead_batch.leads) / total_time if total_time > 0 else 0,
                    "success_rate": lead_batch.metadata.get("success_rate", 0),
                    "avg_confidence": lead_batch.metadata.get("avg_confidence", 0),
                    "timestamp": datetime.now().isoformat(),
                    "phase_times": phase_times,
                    "field_completeness": self._calculate_field_completeness(lead_batch.leads),
                }
                
                return metrics
                
        except Exception as e:
            print(f"ERROR: {str(e)}")
            return {
                "query": query,
                "max_results": max_results,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _calculate_field_completeness(self, leads: List) -> Dict[str, float]:
        """Calculate field population percentage."""
        if not leads:
            return {}
            
        fields = ["name", "role", "linkedin", "company", "company_domain", "email", "phone_number"]
        completeness = {}
        
        for field in fields:
            populated = sum(1 for lead in leads if getattr(lead, field, None))
            completeness[field] = populated / len(leads)
            
        return completeness
    
    async def run_all_benchmarks(self):
        """Run comprehensive benchmark suite."""
        print("\n" + "="*60)
        print("B2B LEAD GENERATION PIPELINE BENCHMARK SUITE")
        print("="*60)
        
        benchmarks = [
            {"query": "CTOs at SaaS companies Berlin", "max_results": 10, "type": "specific"},
            {"query": "Marketing directors at enterprise software companies Germany", "max_results": 15, "type": "medium"},
            {"query": "Tech startups in fintech", "max_results": 20, "type": "broad"},
        ]
        
        all_results = []
        
        for benchmark in benchmarks:
            result = await self.run_benchmark(
                query=benchmark["query"],
                max_results=benchmark["max_results"]
            )
            result["query_type"] = benchmark["type"]
            all_results.append(result)
            
            # Print immediate results
            if "error" not in result:
                print(f"\nResults:")
                print(f"  Leads Found: {result['total_leads_found']}")
                print(f"  Execution Time: {result['total_execution_time']:.2f}s")
                print(f"  Throughput: {result['throughput_leads_per_second']:.2f} leads/sec")
                print(f"  Avg Confidence: {result.get('avg_confidence', 0):.2f}")
            
            # Small delay between benchmarks
            await asyncio.sleep(2)
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.results_dir / f"benchmark_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump({
                "timestamp": timestamp,
                "benchmarks": all_results,
                "summary": self._generate_summary(all_results)
            }, f, indent=2)
        
        print(f"\n{'='*60}")
        print(f"Results saved to: {results_file}")
        print(f"{'='*60}")
        
        self._print_summary(all_results)
        
        return all_results
    
    def _generate_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics."""
        successful = [r for r in results if "error" not in r]
        
        if not successful:
            return {"status": "all_failed"}
        
        total_leads = sum(r["total_leads_found"] for r in successful)
        avg_time = sum(r["total_execution_time"] for r in successful) / len(successful)
        avg_confidence = sum(r.get("avg_confidence", 0) for r in successful) / len(successful)
        
        return {
            "total_benchmarks": len(results),
            "successful_benchmarks": len(successful),
            "failed_benchmarks": len(results) - len(successful),
            "total_leads_found": total_leads,
            "avg_execution_time": avg_time,
            "avg_confidence": avg_confidence,
            "avg_throughput": sum(r.get("throughput_leads_per_second", 0) for r in successful) / len(successful)
        }
    
    def _print_summary(self, results: List[Dict[str, Any]]):
        """Print summary report."""
        summary = self._generate_summary(results)
        
        print("\n" + "="*60)
        print("BENCHMARK SUMMARY")
        print("="*60)
        print(f"Total Benchmarks: {summary.get('total_benchmarks', 0)}")
        print(f"Successful: {summary.get('successful_benchmarks', 0)}")
        print(f"Failed: {summary.get('failed_benchmarks', 0)}")
        print(f"\nPerformance Metrics:")
        print(f"  Total Leads Found: {summary.get('total_leads_found', 0)}")
        print(f"  Avg Execution Time: {summary.get('avg_execution_time', 0):.2f}s")
        print(f"  Avg Throughput: {summary.get('avg_throughput', 0):.2f} leads/sec")
        print(f"  Avg Confidence: {summary.get('avg_confidence', 0):.2f}")
        print("="*60)

async def main():
    """Main benchmark execution."""
    benchmark = PipelineBenchmark()
    await benchmark.run_all_benchmarks()

if __name__ == "__main__":
    asyncio.run(main())
