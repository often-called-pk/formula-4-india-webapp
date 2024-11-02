from flask import Flask, render_template, request, jsonify
import base64
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return render_template('index - Copy.html')

# Helper function to load metadata and telemetry
def load_data(file_path):
    metadata_df = pd.read_csv(file_path, nrows=14, header=None, engine='python')
    telemetry_df = pd.read_csv(file_path, skiprows=14, low_memory=False)
    
    for col in telemetry_df.columns:
        telemetry_df[col] = pd.to_numeric(telemetry_df[col], errors='coerce')
    
    return metadata_df, telemetry_df

# Helper function to convert segment times
def convert_time_to_seconds(time_str):
    try:
        minutes, seconds = map(float, time_str.split(':'))
        return minutes * 60 + seconds
    except ValueError:
        return np.nan

# Helper function to extract fastest lap telemetry data
def get_fastest_lap_data(metadata_df, telemetry_df):
    segment_times_raw = metadata_df.iloc[12].values[1:]
    
    # Convert segment times to seconds
    segment_times = [convert_time_to_seconds(time) for time in segment_times_raw if isinstance(time, str)]
    
    # Remove outliers for lap times (acceptable range: 95 to 120 seconds)
    laps_array = [time for time in segment_times if 95 <= time <= 120]
    
    # Calculate start and end timestamps for the fastest lap
    fastest_lap_time = min(laps_array)
    fastest_lap_index = segment_times.index(fastest_lap_time)
    
    start_time_stamp = sum(segment_times[:fastest_lap_index])
    end_time_stamp = sum(segment_times[:fastest_lap_index + 1])
    
    # Filter telemetry data for the fastest lap
    telemetry_FL = telemetry_df[(telemetry_df['Time'] >= start_time_stamp) & (telemetry_df['Time'] <= end_time_stamp)]
    
    # Adjust the distance calculation to be relative to the start of the fastest lap
    start_distance = telemetry_FL['Distance on Vehicle Speed'].iloc[0]
    telemetry_FL['Distance'] = telemetry_FL['Distance on Vehicle Speed'] - start_distance
    
    return telemetry_FL

# Helper function to classify telemetry actions more accurately
def classify_actions(telemetry_FL):
    throttle_threshold = 90
    brake_pos_median = telemetry_FL['Brake Pos'].median()
    brake_press_median = telemetry_FL['Brake Press'].median()
    
    # Update to classify actions more accurately
    telemetry_FL['Action'] = 'Turning'  # Default action is Turning
    telemetry_FL.loc[telemetry_FL['Throttle Pos'] > throttle_threshold, 'Action'] = 'Full Throttle'
    telemetry_FL.loc[(telemetry_FL['Brake Pos'] > brake_pos_median) & 
                     (telemetry_FL['Brake Press'] > brake_press_median), 'Action'] = 'Brake'
    
    return telemetry_FL

# Function to prompt user to select two files
def select_files():
    Tk().withdraw()  # Close the root window
    print("Please select the first file:")
    file_path_car1 = askopenfilename()
    print(f"First file selected: {file_path_car1}")
    
    print("Please select the second file:")
    file_path_car2 = askopenfilename()
    print(f"Second file selected: {file_path_car2}")
    
    return file_path_car1, file_path_car2

def normalize_and_calculate_delta(telemetry_FL_car1, telemetry_FL_car2):
    # Normalize time to start from zero for both drivers
    telemetry_FL_car1['Normalized Time'] = telemetry_FL_car1['Time'] - telemetry_FL_car1['Time'].iloc[0]
    telemetry_FL_car2['Normalized Time'] = telemetry_FL_car2['Time'] - telemetry_FL_car2['Time'].iloc[0]
    
    # Interpolating time over distance for alignment
    car1_interp = pd.Series(telemetry_FL_car1['Normalized Time'].values, index=telemetry_FL_car1['Distance']).reindex(
        telemetry_FL_car2['Distance'], method="nearest"
    )
    car2_interp = pd.Series(telemetry_FL_car2['Normalized Time'].values, index=telemetry_FL_car2['Distance'])
    
    # Calculating the time delta (car2 - car1)
    lap_delta = car2_interp - car1_interp
    return lap_delta

# Main function to generate plot
def generate_plot(file_path_car1,file_path_car2):

    # Load data for both cars
    metadata_df_car1, telemetry_df_car1 = load_data(file_path_car1)
    metadata_df_car2, telemetry_df_car2 = load_data(file_path_car2)

    # Get fastest lap telemetry for both cars
    telemetry_FL_car1 = get_fastest_lap_data(metadata_df_car1, telemetry_df_car1)
    telemetry_FL_car2 = get_fastest_lap_data(metadata_df_car2, telemetry_df_car2)

    # Classify actions for both cars
    telemetry_FL_car1 = classify_actions(telemetry_FL_car1)
    telemetry_FL_car2 = classify_actions(telemetry_FL_car2)
    
    # Calculate lap delta
    lap_delta = normalize_and_calculate_delta(telemetry_FL_car1, telemetry_FL_car2)
    
    # Extract driver and vehicle information
    driver_name_car1 = metadata_df_car1.iloc[3, 1]
    driver_name_car2 = metadata_df_car2.iloc[3, 1]

    # Create subplots with shared x-axis
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, 
                        subplot_titles=[f"{driver_name_car1} vs {driver_name_car2} Speed",
                                        "Lap Delta (Time Difference)",
                                        f"{driver_name_car1} Actions",
                                        f"{driver_name_car2} Actions"],
                        row_heights=[0.4, 0.2, 0.2, 0.2], vertical_spacing=0.05)
    
    # Speed plot (top)
    fig.add_trace(go.Scatter(x=telemetry_FL_car1['Distance'], y=telemetry_FL_car1['Speed'],
                             mode='lines', name=f'{driver_name_car1} Speed', line=dict(color='orange')),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=telemetry_FL_car2['Distance'], y=telemetry_FL_car2['Speed'],
                             mode='lines', name=f'{driver_name_car2} Speed', line=dict(color='cyan')),
                  row=1, col=1)

    # Lap Delta plot (second row)
    fig.add_trace(go.Scatter(x=telemetry_FL_car2['Distance'], y=lap_delta,
                             mode='lines', name=f'Delta ({driver_name_car2})', line=dict(color='cyan')),
                  row=2, col=1)
    fig.add_trace(go.Scatter(x=telemetry_FL_car2['Distance'], y=[0] * len(telemetry_FL_car2['Distance']),
                             mode='lines', name='Zero Reference', line=dict(color='gray', dash='dash')),
                  row=2, col=1)

    # Define action colors
    action_colors = {'Brake': 'red', 'Full Throttle': 'green', 'Turning': 'yellow'}
    legend_added = {'Brake': False, 'Full Throttle': False, 'Turning': False}

    # Function to plot action bars with constant height
    def plot_action_bars(telemetry_data, driver_name, row_idx):
        action_changes = telemetry_data['Action'].ne(telemetry_data['Action'].shift()).cumsum()
        telemetry_data['ActionID'] = action_changes
        grouped_actions = telemetry_data.groupby('ActionID')
        
        for _, group in grouped_actions:
            action_type = group['Action'].iloc[0]
            color = action_colors[action_type]
            show_legend = not legend_added[action_type]
            if show_legend:
                legend_added[action_type] = True
            
            fig.add_trace(go.Bar(x=[group['Distance'].max() - group['Distance'].min()], 
                             y=[driver_name],  # Constant y-value
                             marker_color=color,
                             width=[50],
                             base=group['Distance'].min(), 
                             orientation='h', name=f'{action_type}' if show_legend else None,
                             showlegend=show_legend),
                      row=row_idx, col=1)

    # Plot action bars for the first car
    plot_action_bars(telemetry_FL_car1, driver_name_car1, 3)

    # Plot action bars for the second car
    plot_action_bars(telemetry_FL_car2, driver_name_car2, 4)
    
    # Update layout
    fig.update_layout(height=1200, width=2000, title_text="Telemetry Data Comparison: Fastest Lap",
                      template="plotly_dark",
                      font=dict(color='white'),
                      showlegend=True,
                      legend=dict(font=dict(color='white')))
    
    # Set axis titles and colors
    fig.update_xaxes(title_text="Distance (m)", row=4, col=1, title_font=dict(color='white'), tickfont=dict(color='white'))
    fig.update_yaxes(title_text="Speed (km/h)", row=1, col=1, title_font=dict(color='white'), tickfont=dict(color='white'))
    fig.update_yaxes(title_text="Time Delta (s)", row=2, col=1, title_font=dict(color='white'), tickfont=dict(color='white'))
    
    # Set subplot title font color
    fig.update_annotations(font=dict(color='white'))

    # Show the plot
    fig.show()


@app.route('/generate', methods=['POST'])
def generate():
    if 'file1' not in request.files or 'file2' not in request.files:
        return "Both files are required", 400

    file1 = request.files['file1']
    file2 = request.files['file2']

    # Generate the plot using the uploaded files
    fig = generate_plot(file1, file2)
    graph_html = fig.to_html(full_html=False)

    return render_template('generate.html', plot=graph_html)

if __name__ == "__main__":
    app.run(debug=True)