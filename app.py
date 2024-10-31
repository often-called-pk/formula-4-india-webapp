from flask import Flask, render_template, request, jsonify
import base64
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
import fastf1 as ff1

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# Helper functions
def load_data(file_path):
    metadata_df = pd.read_csv(file_path, nrows=14, header=None, engine='python')
    telemetry_df = pd.read_csv(file_path, skiprows=14, low_memory=False)
    for col in telemetry_df.columns:
        telemetry_df[col] = pd.to_numeric(telemetry_df[col], errors='coerce')
    return metadata_df, telemetry_df

def convert_time_to_seconds(time_str):
    try:
        minutes, seconds = map(float, time_str.split(':'))
        return minutes * 60 + seconds
    except ValueError:
        return np.nan

def get_fastest_lap_data(metadata_df, telemetry_df):
    segment_times_raw = metadata_df.iloc[12].values[1:]
    segment_times = [convert_time_to_seconds(time) for time in segment_times_raw if isinstance(time, str)]
    laps_array = [time for time in segment_times if 95 <= time <= 120]
    fastest_lap_time = min(laps_array)
    fastest_lap_index = segment_times.index(fastest_lap_time)
    start_time_stamp = sum(segment_times[:fastest_lap_index])
    end_time_stamp = sum(segment_times[:fastest_lap_index + 1])
    telemetry_FL = telemetry_df[(telemetry_df['Time'] >= start_time_stamp) & (telemetry_df['Time'] <= end_time_stamp)]
    start_distance = telemetry_FL['Distance on Vehicle Speed'].iloc[0]
    telemetry_FL['Distance'] = telemetry_FL['Distance on Vehicle Speed'] - start_distance
    return telemetry_FL

def classify_actions(telemetry_FL):
    throttle_threshold = 90
    brake_pos_median = telemetry_FL['Brake Pos'].median()
    brake_press_median = telemetry_FL['Brake Press'].median()
    telemetry_FL['Action'] = 'Turning'
    telemetry_FL.loc[telemetry_FL['Throttle Pos'] > throttle_threshold, 'Action'] = 'Full Throttle'
    telemetry_FL.loc[(telemetry_FL['Brake Pos'] > brake_pos_median) & 
                     (telemetry_FL['Brake Press'] > brake_press_median), 'Action'] = 'Brake'
    return telemetry_FL

# Generate plot function for telemetry comparison
def generate_plot(file_path_car1, file_path_car2):
    metadata_df_car1, telemetry_df_car1 = load_data(file_path_car1)
    metadata_df_car2, telemetry_df_car2 = load_data(file_path_car2)
    telemetry_FL_car1 = get_fastest_lap_data(metadata_df_car1, telemetry_df_car1)
    telemetry_FL_car2 = get_fastest_lap_data(metadata_df_car2, telemetry_df_car2)
    telemetry_FL_car1 = classify_actions(telemetry_FL_car1)
    telemetry_FL_car2 = classify_actions(telemetry_FL_car2)
    lap_delta = normalize_and_calculate_delta(telemetry_FL_car1, telemetry_FL_car2)

    # Set up Plotly figure
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, 
                        subplot_titles=["Driver Speed Comparison", "Lap Delta (Time Difference)",
                                        "Driver 1 Actions", "Driver 2 Actions"],
                        row_heights=[0.4, 0.2, 0.2, 0.2], vertical_spacing=0.05)
    # Add speed, delta, and actions (similar to the original code)
    # Insert Plotly traces here for each plot segment as in the original script.

    return fig

@app.route('/generate', methods=['GET', 'POST'])

def generate():

    # Get the 'data' parameter from the query string
    base64_json = request.args.get('data')

    if not base64_json:
        return jsonify({"error": "No data parameter provided"}), 400

    if 'file_car1' not in request.files or 'file_car2' not in request.files:
        return jsonify({"error": "Both files are required."}), 400
    
    
    file_car1 = request.files['file_car1']
    file_car2 = request.files['file_car2']
    
    fig = generate_plot(file_car1, file_car2)
    graph_html = fig.to_html(full_html=False)

    return render_template('generate.html', plot=graph_html)

if __name__ == "__main__":
    app.run(debug=True)
