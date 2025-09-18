#!/usr/bin/env python3

import os
import json
import time
import requests
import subprocess
import threading
import glob
from typing import Dict, List, Any
from dataclasses import dataclass
import pandas as pd
from datetime import datetime

@dataclass
class TestResult:
    provider: str
    endpoint: str
    method: str
    latency_ms: float
    price_usd: float
    score: float
    weights: Dict[str, float]
    response_data: Dict[str, Any]
    timestamp: float

class ComprehensiveTestRunner:
    def __init__(self, base_url="http://localhost:6969"):
        self.base_url = base_url
        self.test_data_dir = "/Users/sambhavjain/Desktop/bliply/bliply/test_data"
        self.results = []
        self.server_process = None
        
    def load_test_requests(self) -> List[Dict[str, Any]]:
        """Load RPC requests from test_data directory"""
        test_requests = []
        
        # Find all .io files in test_data
        io_files = glob.glob(f"{self.test_data_dir}/**/*.io", recursive=True)
        
        for file_path in io_files:  # Process all test files
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                # Parse the .io file format (>> request, << response)
                lines = content.strip().split('\n')
                for line in lines:
                    if line.startswith('>>'):
                        request_json = line[2:].strip()
                        try:
                            request_data = json.loads(request_json)
                            test_requests.append({
                                'file': os.path.basename(file_path),
                                'method': request_data.get('method', 'unknown'),
                                'request': request_data
                            })
                        except json.JSONDecodeError:
                            continue
                            
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                continue
                
        return test_requests
        
    
    def run_rpc_request(self, provider: str, request_data: Dict[str, Any]) -> TestResult:
        """Run a single RPC request against a provider"""
        endpoint = f"/rpc/{provider}"
        url = f"{self.base_url}{endpoint}"
        
        start_time = time.time()
        
        try:
            response = requests.post(url, json=request_data['request'], timeout=10)
            response_json = response.json()
            
            return TestResult(
                provider=provider,
                endpoint=endpoint,
                method=request_data['method'],
                latency_ms=response_json.get('latency_ms'),
                price_usd=response_json.get('price_usd'),
                score=response_json.get('score'),
                weights=response_json.get('weights'),
                response_data=response_json,
                timestamp=time.time()
            )
            
        except Exception as e:
            return TestResult(
                provider=provider,
                endpoint=endpoint,
                method=request_data['method'],
                latency_ms=0,
                price_usd=0,
                score=0,
                weights={},
                response_data={'error': str(e)},
                timestamp=time.time()
            )
    
    def run_best_request(self, request_data: Dict[str, Any]) -> TestResult:
        """Run a request against the /rpc/best endpoint"""
        endpoint = "/rpc/best"
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.post(url, json=request_data['request'], timeout=10)
            response_json = response.json()
            
            return TestResult(
                provider="best",
                endpoint=endpoint,
                method=request_data['method'],
                latency_ms=response_json.get('latency_ms', 0),
                price_usd=response_json.get('price_usd', 0),
                score=response_json.get('score', 0),
                weights=response_json.get('weights', {}),
                response_data=response_json,
                timestamp=time.time()
            )
            
        except Exception as e:
            return TestResult(
                provider="best",
                endpoint=endpoint,
                method=request_data['method'],
                latency_ms=0,
                price_usd=0,
                score=0,
                weights={},
                response_data={'error': str(e)},
                timestamp=time.time()
            )
    
    def run_comprehensive_test(self):
        """Run the comprehensive test suite"""
        print("🚀 Starting Comprehensive Test Suite")
        print("=" * 50)
        
        # Load test requests
        print("📁 Loading test requests from test_data...")
        test_requests = self.load_test_requests()
        print(f"✅ Loaded {len(test_requests)} test requests")
        
        
        # Test each request against all providers
        providers = ["alchemy", "chainstack" , "quicknode"]
        
        for i, request_data in enumerate(test_requests):
            print(f"\n📋 Test {i+1}/{len(test_requests)}: {request_data['method']} ({request_data['file']})")
            
            # Test individual providers
            for provider in providers:
                print(f"  🔄 Testing {provider}...")
                result = self.run_rpc_request(provider, request_data)
                self.results.append(result)
                print(f"    ✅ {provider}: Score={result.score:.4f}, Latency={result.latency_ms:.2f}ms, Price=${result.price_usd:.10f}")
            
            # Test best endpoint
            print(f"  🎯 Testing best endpoint...")
            best_result = self.run_best_request(request_data)
            self.results.append(best_result)
            
            selected_provider = best_result.response_data.get('selected_provider', 'unknown')
            print(f"    ✅ Best selected: {selected_provider}, Score={best_result.score:.4f}")
            
            # Small delay between requests
            time.sleep(0.5)
        
        # Generate comparison report
        self.generate_comparison_report()
            
    
    def generate_comparison_report(self):
        """Generate detailed comparison report"""
        print("\n" + "=" * 50)
        print("📊 COMPREHENSIVE COMPARISON REPORT")
        print("=" * 50)
        
        # Convert results to DataFrame for easier analysis
        df_data = []
        for result in self.results:
            df_data.append({
                'Provider': result.provider,
                'Method': result.method,
                'Endpoint': result.endpoint,
                'Latency_ms': result.latency_ms,
                'Price_USD': result.price_usd,
                'Score': result.score,
                'Weight_Latency': result.weights.get('Latency', 0),
                'Weight_Price': result.weights.get('Price', 0),
                'Has_Error': 'error' in result.response_data,
                'Selected_Provider': result.response_data.get('selected_provider', ''),
                'Timestamp': result.timestamp
            })
        
        df = pd.DataFrame(df_data)
        
        if df.empty:
            print("❌ No results to analyze")
            return
        
        # Overall statistics
        print("\n📈 OVERALL STATISTICS")
        print("-" * 30)
        print(f"Total requests tested: {len(df)}")
        print(f"Unique methods tested: {df['Method'].nunique()}")
        print(f"Providers tested: {', '.join(df['Provider'].unique())}")
        print(f"Success rate: {((~df['Has_Error']).sum() / len(df) * 100):.1f}%")
        
        # Provider comparison
        print("\n🏆 PROVIDER PERFORMANCE COMPARISON")
        print("-" * 40)
        
        provider_stats = df[df['Provider'] != 'best'].groupby('Provider').agg({
            'Latency_ms': ['mean', 'std', 'min', 'max'],
            'Price_USD': ['mean', 'std', 'min', 'max'],
            'Score': ['mean', 'std', 'min', 'max'],
            'Has_Error': 'sum'
        }).round(4)
        
        print(provider_stats)
        
        # Best endpoint analysis
        print("\n🎯 BEST ENDPOINT SELECTION ANALYSIS")
        print("-" * 40)
        
        best_selections = df[df['Provider'] == 'best']['Selected_Provider'].value_counts()
        total_selections = best_selections.sum()
        print("Provider selection frequency:")
        for provider, count in best_selections.items():
            if provider:  # Skip empty strings
                percentage = (count / total_selections) * 100
                print(f"  {provider}: {count} times ({percentage:.1f}%)")
        
        # Method-wise analysis
        print("\n📋 METHOD-WISE PERFORMANCE")
        print("-" * 30)
        
        method_stats = df[df['Provider'] != 'best'].groupby(['Method', 'Provider']).agg({
            'Latency_ms': 'mean',
            'Price_USD': 'mean',
            'Score': 'mean'
        }).round(4)
        
        print(method_stats)
        
        # Weight analysis
        print("\n⚖️ DYNAMIC WEIGHT ANALYSIS")
        print("-" * 30)
        
        weight_stats = df.groupby('Provider').agg({
            'Weight_Latency': ['mean', 'std'],
            'Weight_Price': ['mean', 'std']
        }).round(4)
        
        print(weight_stats)
        
        # Save detailed results to JSON and Excel
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"/Users/sambhavjain/Desktop/bliply/test_results_{timestamp}.json"
        excel_file = f"/Users/sambhavjain/Desktop/bliply/test_results_{timestamp}.xlsx"
        
        # Convert DataFrames to serializable format
        provider_stats_dict = {}
        for provider in provider_stats.index:
            provider_stats_dict[provider] = {
                'latency_ms_mean': float(provider_stats.loc[provider, ('Latency_ms', 'mean')]),
                'latency_ms_std': float(provider_stats.loc[provider, ('Latency_ms', 'std')]),
                'latency_ms_min': float(provider_stats.loc[provider, ('Latency_ms', 'min')]),
                'latency_ms_max': float(provider_stats.loc[provider, ('Latency_ms', 'max')]),
                'price_usd_mean': float(provider_stats.loc[provider, ('Price_USD', 'mean')]),
                'price_usd_std': float(provider_stats.loc[provider, ('Price_USD', 'std')]),
                'price_usd_min': float(provider_stats.loc[provider, ('Price_USD', 'min')]),
                'price_usd_max': float(provider_stats.loc[provider, ('Price_USD', 'max')]),
                'score_mean': float(provider_stats.loc[provider, ('Score', 'mean')]),
                'score_std': float(provider_stats.loc[provider, ('Score', 'std')]),
                'score_min': float(provider_stats.loc[provider, ('Score', 'min')]),
                'score_max': float(provider_stats.loc[provider, ('Score', 'max')]),
                'error_count': int(provider_stats.loc[provider, ('Has_Error', 'sum')])
            }
        
        method_stats_dict = {}
        for (method, provider), row in method_stats.iterrows():
            key = f"{method}_{provider}"
            method_stats_dict[key] = {
                'method': method,
                'provider': provider,
                'latency_ms': float(row['Latency_ms']),
                'price_usd': float(row['Price_USD']),
                'score': float(row['Score'])
            }
        
        weight_stats_dict = {}
        for provider in weight_stats.index:
            weight_stats_dict[provider] = {
                'weight_latency_mean': float(weight_stats.loc[provider, ('Weight_Latency', 'mean')]),
                'weight_latency_std': float(weight_stats.loc[provider, ('Weight_Latency', 'std')]),
                'weight_price_mean': float(weight_stats.loc[provider, ('Weight_Price', 'mean')]),
                'weight_price_std': float(weight_stats.loc[provider, ('Weight_Price', 'std')])
            }
        
        detailed_results = {
            'summary': {
                'total_requests': len(df),
                'unique_methods': df['Method'].nunique(),
                'providers': df['Provider'].unique().tolist(),
                'success_rate': float((~df['Has_Error']).sum() / len(df) * 100)
            },
            'provider_stats': provider_stats_dict,
            'best_selections': dict(best_selections),
            'method_stats': method_stats_dict,
            'weight_stats': weight_stats_dict,
            'raw_results': [
                {
                    'provider': r.provider,
                    'method': r.method,
                    'endpoint': r.endpoint,
                    'latency_ms': r.latency_ms,
                    'price_usd': r.price_usd,
                    'score': r.score,
                    'weights': r.weights,
                    'response_data': r.response_data,
                    'timestamp': r.timestamp
                }
                for r in self.results
            ]
        }
        
        with open(results_file, 'w') as f:
            json.dump(detailed_results, f, indent=2, default=str)
        
        # Export to Excel
        self.export_to_excel(df, provider_stats, best_selections, method_stats, weight_stats, excel_file)
        
        print(f"\n💾 Results saved:")
        print(f"   JSON: {results_file}")
        print(f"   Excel: {excel_file}")
        
        # Parameter change analysis
        self.analyze_parameter_changes()
    
    def export_to_excel(self, df, provider_stats, best_selections, method_stats, weight_stats, excel_file):
        """Export all data to Excel with multiple sheets"""
        try:
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # Sheet 1: Raw Results
                df_export = df.copy()
                df_export['Timestamp_Readable'] = pd.to_datetime(df_export['Timestamp'], unit='s')
                df_export.to_excel(writer, sheet_name='Raw_Results', index=False)
                
                # Sheet 2: Provider Statistics
                provider_stats_flat = pd.DataFrame()
                for provider in provider_stats.index:
                    row_data = {
                        'Provider': provider,
                        'Avg_Latency_ms': provider_stats.loc[provider, ('Latency_ms', 'mean')],
                        'Std_Latency_ms': provider_stats.loc[provider, ('Latency_ms', 'std')],
                        'Min_Latency_ms': provider_stats.loc[provider, ('Latency_ms', 'min')],
                        'Max_Latency_ms': provider_stats.loc[provider, ('Latency_ms', 'max')],
                        'Avg_Price_USD': provider_stats.loc[provider, ('Price_USD', 'mean')],
                        'Std_Price_USD': provider_stats.loc[provider, ('Price_USD', 'std')],
                        'Min_Price_USD': provider_stats.loc[provider, ('Price_USD', 'min')],
                        'Max_Price_USD': provider_stats.loc[provider, ('Price_USD', 'max')],
                        'Avg_Score': provider_stats.loc[provider, ('Score', 'mean')],
                        'Std_Score': provider_stats.loc[provider, ('Score', 'std')],
                        'Min_Score': provider_stats.loc[provider, ('Score', 'min')],
                        'Max_Score': provider_stats.loc[provider, ('Score', 'max')],
                        'Error_Count': provider_stats.loc[provider, ('Has_Error', 'sum')]
                    }
                    provider_stats_flat = pd.concat([provider_stats_flat, pd.DataFrame([row_data])], ignore_index=True)
                
                provider_stats_flat.to_excel(writer, sheet_name='Provider_Statistics', index=False)
                
                # Sheet 3: Best Selection Analysis
                best_df = pd.DataFrame(list(best_selections.items()), columns=['Selected_Provider', 'Selection_Count'])
                best_df['Selection_Percentage'] = (best_df['Selection_Count'] / best_df['Selection_Count'].sum() * 100).round(2)
                best_df.to_excel(writer, sheet_name='Best_Selections', index=False)
                
                # Sheet 4: Method-wise Performance
                method_stats_flat = method_stats.reset_index()
                method_stats_flat.columns = ['Method', 'Provider', 'Avg_Latency_ms', 'Avg_Price_USD', 'Avg_Score']
                method_stats_flat.to_excel(writer, sheet_name='Method_Performance', index=False)
                
                # Sheet 5: Weight Analysis
                weight_stats_flat = pd.DataFrame()
                for provider in weight_stats.index:
                    row_data = {
                        'Provider': provider,
                        'Avg_Weight_Latency': weight_stats.loc[provider, ('Weight_Latency', 'mean')],
                        'Std_Weight_Latency': weight_stats.loc[provider, ('Weight_Latency', 'std')],
                        'Avg_Weight_Price': weight_stats.loc[provider, ('Weight_Price', 'mean')],
                        'Std_Weight_Price': weight_stats.loc[provider, ('Weight_Price', 'std')]
                    }
                    weight_stats_flat = pd.concat([weight_stats_flat, pd.DataFrame([row_data])], ignore_index=True)
                
                weight_stats_flat.to_excel(writer, sheet_name='Weight_Analysis', index=False)
                
                # Sheet 6: Summary Statistics
                summary_data = {
                    'Metric': [
                        'Total Requests',
                        'Unique Methods',
                        'Success Rate (%)',
                        'Average Latency (ms)',
                        'Average Price (USD)',
                        'Average Score'
                    ],
                    'Value': [
                        len(df),
                        df['Method'].nunique(),
                        round((~df['Has_Error']).sum() / len(df) * 100, 2),
                        round(df[df['Provider'] != 'best']['Latency_ms'].mean(), 4),
                        round(df[df['Provider'] != 'best']['Price_USD'].mean(), 10),
                        round(df[df['Provider'] != 'best']['Score'].mean(), 4)
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # Sheet 7: Detailed Response Data
                response_details = []
                for result in self.results:
                    response_details.append({
                        'Provider': result.provider,
                        'Method': result.method,
                        'Endpoint': result.endpoint,
                        'Latency_ms': result.latency_ms,
                        'Price_USD': result.price_usd,
                        'Score': result.score,
                        'Weight_Latency': result.weights.get('Latency', 0),
                        'Weight_Price': result.weights.get('Price', 0),
                        'Selected_Provider': result.response_data.get('selected_provider', ''),
                        'Has_Error': 'error' in result.response_data,
                        'Error_Message': result.response_data.get('error', ''),
                        'Response_Keys': ', '.join(result.response_data.keys()),
                        'Timestamp': result.timestamp,
                        'Timestamp_Readable': datetime.fromtimestamp(result.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    })
                
                response_df = pd.DataFrame(response_details)
                response_df.to_excel(writer, sheet_name='Detailed_Responses', index=False)
                
            print(f"✅ Excel export completed: {excel_file}")
            
        except Exception as e:
            print(f"❌ Error exporting to Excel: {e}")
            print("Make sure you have openpyxl installed: pip install openpyxl")
    
    def analyze_parameter_changes(self):
        """Analyze how parameters change across different RPC requests"""
        print("\n🔄 PARAMETER CHANGE ANALYSIS")
        print("-" * 35)
        
        # Group results by method and provider
        method_provider_groups = {}
        for result in self.results:
            key = f"{result.method}_{result.provider}"
            if key not in method_provider_groups:
                method_provider_groups[key] = []
            method_provider_groups[key].append(result)
        
        # Analyze parameter variations
        for key, results in method_provider_groups.items():
            if len(results) > 1:
                method, provider = key.rsplit('_', 1)
                print(f"\n📊 {method} on {provider}:")
                
                latencies = [r.latency_ms for r in results]
                prices = [r.price_usd for r in results]
                scores = [r.score for r in results]
                
                print(f"  Latency variation: {min(latencies):.2f} - {max(latencies):.2f}ms (σ={pd.Series(latencies).std():.2f})")
                print(f"  Price variation: ${min(prices):.10f} - ${max(prices):.10f} (σ=${pd.Series(prices).std():.10f})")
                print(f"  Score variation: {min(scores):.4f} - {max(scores):.4f} (σ={pd.Series(scores).std():.4f})")

def main():
    """Main function to run the comprehensive test"""
    print("🧪 Bliply Comprehensive Test Suite")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists("/Users/sambhavjain/Desktop/bliply/bliply/main.py"):
        print("❌ Error: main.py not found. Please run from the correct directory.")
        return
    
    # Check if test_data exists
    if not os.path.exists("/Users/sambhavjain/Desktop/bliply/bliply/test_data"):
        print("❌ Error: test_data directory not found.")
        return
    
    # Run the comprehensive test
    runner = ComprehensiveTestRunner()
    runner.run_comprehensive_test()
    
    print("\n✅ Comprehensive test completed!")
    print("Check test_results.json for detailed analysis.")

if __name__ == "__main__":
    main()
