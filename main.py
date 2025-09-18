import threading
import queue
from flask import Flask, request, jsonify
from data.providers import load_providers
from strategy.scoring_engine import calculate_dynamic_scores
from data.metrics import get_latest_provider_snapshot, get_all_historical_data

app = Flask(__name__)
providers = load_providers()
provider_dict = {p.name.lower(): p for p in providers}

# method -> worker
method_workers = {}

class MethodWorker:
    def __init__(self, method):
        self.method = method
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        while True:
            payload, result_q = self.queue.get()
            try:
                historical_df = get_all_historical_data(providers, method=self.method)
                latest_df = get_latest_provider_snapshot(providers, method=self.method)
                scored_df, weights = calculate_dynamic_scores(providers, method=self.method)

                if latest_df.empty:
                    result_q.put({"error": f"No providers available for {self.method}"})
                    continue

                latest_df["Lnorm"] = 1 - (latest_df["Latency"] - latest_df["Latency"].min()) / \
                                    max(latest_df["Latency"].max() - latest_df["Latency"].min(), 1e-10)
                latest_df["Pnorm"] = 1 - (latest_df["Price"] - latest_df["Price"].min()) / \
                                    max(latest_df["Price"].max() - latest_df["Price"].min(), 1e-10)
                latest_df["Score"] = latest_df["Lnorm"] * weights[0] + latest_df["Pnorm"] * weights[1]

                eligible_df = latest_df[latest_df["Eligible"] == True]
                if eligible_df.empty:
                    eligible_df = latest_df

                eligible_df = eligible_df[eligible_df["Provider"].str.lower() != "best"]
                if eligible_df.empty:
                    result_q.put({"error": f"No eligible real providers for {self.method}"})
                    continue

                best_row = eligible_df.loc[eligible_df["Score"].idxmax()]
                best_provider_name = best_row["Provider"]
                best_provider = provider_dict[best_provider_name.lower()]

                response = best_provider.call(payload, all_providers=providers)

                best_virtual = provider_dict["best"]
                best_virtual.metrics.add_record(
                    provider="Best",
                    method=self.method,
                    latency_ms=response.get("latency_ms", best_row["Latency"]),
                    price=response.get("price_usd", best_row["Price"]),
                )

                response.update({
                    "score": float(best_row["Score"]),
                    "weights": {"Latency": float(weights[0]), "Price": float(weights[1])},
                    "selected_provider": best_provider_name,
                    "all_provider_scores": {
                        row["Provider"]: {
                            "score": float(row["Score"]),
                            "latency": float(row["Latency"]),
                            "price": float(row["Price"])
                        }
                        for _, row in latest_df.iterrows()
                    }
                })

                print(f"[RPC Best -> {best_provider.name}] {self.method} "
                    f"→ Selected Provider: {best_provider_name}, Score={best_row['Score']:.4f}")

                result_q.put(response)

            except Exception as e:
                result_q.put({"error": f"Worker failed for {self.method}: {str(e)}"})
            finally:
                self.queue.task_done()

    def submit(self, payload):
        result_q = queue.Queue()
        self.queue.put((payload, result_q))
        return result_q.get()


def get_or_create_worker(method: str) -> MethodWorker:
    if method not in method_workers:
        method_workers[method] = MethodWorker(method)
    return method_workers[method]


@app.route("/rpc/<provider_name>", methods=["POST"])
def rpc_provider(provider_name):
    provider = provider_dict.get(provider_name.lower())
    if not provider:
        return jsonify({"error": f"Provider '{provider_name}' not found"}), 404

    payload = request.json
    response = provider.call(payload, all_providers=providers)

    print(f"[RPC {provider.name}] Score: {response['score']:.4f}, "
          f"Weights: L={response['weights']['Latency']:.3f}, P={response['weights']['Price']:.3f}, "
          f"Latency: {response['latency_ms']:.2f}ms, Price: ${response['price_usd']:.4f}")

    return jsonify(response)


@app.route("/rpc/best", methods=["POST"])
def rpc_best():
    payload = request.json
    method = payload.get("method")
    if not method:
        return jsonify({"error": "No RPC method specified"}), 400

    worker = get_or_create_worker(method)
    result = worker.submit(payload)
    return jsonify(result)


@app.route("/records", methods=["GET"])
def records():
    try:
        method = request.args.get("method")  # optional filter
        all_records = []

        for provider in providers:
            df = provider.metrics.get_all_records(method)
            if not df.empty:
                all_records.extend(df.to_dict(orient="records"))

        return jsonify({
            "method": method if method else "all",
            "records": all_records,
            "total_records": len(all_records)
        })

    except Exception as e:
        return jsonify({"error": f"Failed to fetch records: {str(e)}"}), 500


@app.route("/analytics", methods=["GET"])
def analytics():
    try:
        method = request.args.get("method")
        if not method:
            return jsonify({"error": "Please provide a method (e.g., ?method=eth_blockNumber)"}), 400

        latest_df = get_latest_provider_snapshot(providers, method=method)

        analytics_data = {
            "method": method,
            "providers": [],
            "total_records": sum(len(p.metrics.get_all_records(method)) for p in providers)
        }

        for _, row in latest_df.iterrows():
            provider_name = row["Provider"]
            provider_obj = provider_dict[provider_name.lower()]
            records = provider_obj.metrics.get_all_records(method)

            analytics_data["providers"].append({
                "name": provider_name,
                "avg_latency_ms": float(row["Latency"]),
                "avg_price_usd": float(row["Price"]),
                "eligible": bool(row["Eligible"]),
                "record_count": len(records),
                "normalized_latency": float(row.get("Lnorm", 0)),
                "normalized_price": float(row.get("Pnorm", 0))
            })

        return jsonify(analytics_data)

    except Exception as e:
        return jsonify({"error": f"Failed to generate analytics: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6969, debug=True)
