from flask import Flask, request, jsonify
from data.providers import load_providers
from strategy.scoring_engine import calculate_dynamic_scores
from data.metrics import get_latest_provider_snapshot, get_all_historical_data

app = Flask(__name__)
providers = load_providers()
provider_dict = {p.name.lower(): p for p in providers}


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
    try:
        # Step 1: Get historical data
        historical_df = get_all_historical_data(providers)

        # Step 2: Get latest snapshot
        latest_df = get_latest_provider_snapshot(providers)

        if latest_df.empty:
            return jsonify({"error": "No providers available"}), 500

        # Step 3: Compute CRITIC weights from historical data
        criteria = ["Latency", "Price"]
        # Normalize historical data for CRITIC weight calculation
        norm_hist = latest_df.copy()
        norm_hist["Lnorm"] = 1 - (norm_hist["Latency"] - norm_hist["Latency"].min()) / \
                             max(norm_hist["Latency"].max() - norm_hist["Latency"].min(), 1e-10)
        norm_hist["Pnorm"] = 1 - (norm_hist["Price"] - norm_hist["Price"].min()) / \
                             max(norm_hist["Price"].max() - norm_hist["Price"].min(), 1e-10)

        
        scored_df, weights = calculate_dynamic_scores(providers)  # returns weights as [wLatency, wPrice]

        # Step 4: Compute scores for all providers
        latest_df["Lnorm"] = 1 - (latest_df["Latency"] - latest_df["Latency"].min()) / \
                             max(latest_df["Latency"].max() - latest_df["Latency"].min(), 1e-10)
        latest_df["Pnorm"] = 1 - (latest_df["Price"] - latest_df["Price"].min()) / \
                             max(latest_df["Price"].max() - latest_df["Price"].min(), 1e-10)
        latest_df["Score"] = latest_df["Lnorm"] * weights[0] + latest_df["Pnorm"] * weights[1]

        # Step 5: Filter eligible providers
        eligible_df = latest_df[latest_df["Eligible"] == True]
        if eligible_df.empty:
            eligible_df = latest_df

        # Step 6: Select best provider
        best_row = eligible_df.loc[eligible_df["Score"].idxmax()]
        best_provider_name = best_row["Provider"]
        best_provider = provider_dict[best_provider_name.lower()]

        # Step 7: Forward the request to the selected provider
        response = best_provider.call(payload, all_providers=providers)

        # Step 8: Include all scoring info
        response.update({
            "score": float(best_row["Score"]),
            "weights": {"Latency": float(weights[0]), "Price": float(weights[1])},
            "selected_provider": best_provider_name,
            "all_provider_scores": {
                row["Provider"]: {"score": float(row["Score"]),
                                  "latency": float(row["Latency"]),
                                  "price": float(row["Price"])}
                for _, row in latest_df.iterrows()
            }
        })

        print(f"\n[RPC Best -> {best_provider.name}] Selected Provider: {best_provider_name}, Score: {best_row['Score']:.4f}")

    except Exception as e:
        print(f"Error in /rpc/best: {e}")
        return jsonify({"error": f"Failed to calculate best provider: {str(e)}"}), 500

    return jsonify(response)



@app.route("/records", methods=["GET"])
def records():
    all_records = []
    for provider in providers:
        all_records.extend(provider.metrics.get_records())
    return jsonify(all_records)


@app.route("/analytics", methods=["GET"])
def analytics():
    """Endpoint to see current provider analytics and CRITIC weights."""
    try:

        scored_df, weights = calculate_dynamic_scores(providers)
        latest_df = get_latest_provider_snapshot(providers)

        analytics_data = {
            "weights": {
                "Latency": float(weights[0]),
                "Price": float(weights[1])
            },
            "providers": [],
            "total_records": sum(len(p.metrics.get_records()) for p in providers)
        }

        for _, row in latest_df.iterrows():
            provider_name = row["Provider"]
            provider_obj = provider_dict[provider_name.lower()]
            records = provider_obj.metrics.get_records()

            analytics_data["providers"].append({
                "name": provider_name,
                "score": float(row["Score"]) if "Score" in row else 0,
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
    app.run(host="0.0.0.0", port=5000, debug=True)
