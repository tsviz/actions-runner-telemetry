#!/usr/bin/env python3
"""
Generate sophisticated visual telemetry report with time-series graphs.
Creates SVG charts and markdown summary for GITHUB_STEP_SUMMARY.
Enhanced with modern gradients, animations, and intuitive visualizations.
"""

import os
import sys
import json
import math
from datetime import datetime
from pathlib import Path

DATA_FILE = os.environ.get('TELEMETRY_DATA_FILE', '/tmp/telemetry_data.json')

# Modern color palette with gradients
COLORS = {
    'primary': '#3b82f6',
    'primary_light': '#60a5fa',
    'primary_dark': '#1d4ed8',
    'secondary': '#8b5cf6', 
    'secondary_light': '#a78bfa',
    'success': '#22c55e',
    'success_light': '#4ade80',
    'warning': '#eab308',
    'warning_light': '#fde047',
    'danger': '#ef4444',
    'danger_light': '#f87171',
    'info': '#06b6d4',
    'info_light': '#22d3ee',
    'gray': '#6b7280',
    'gray_light': '#9ca3af',
    'dark': '#1f2937',
    'light': '#f3f4f6',
    'white': '#ffffff',
    'cpu': '#3b82f6',
    'cpu_gradient': ['#3b82f6', '#60a5fa'],
    'memory': '#8b5cf6',
    'memory_gradient': ['#8b5cf6', '#a78bfa'],
    'disk_read': '#22c55e',
    'disk_write': '#f97316',
    'net_rx': '#06b6d4',
    'net_tx': '#ec4899',
    'load': '#eab308',
    # Status colors
    'status_good': '#10b981',
    'status_warning': '#f59e0b', 
    'status_critical': '#ef4444',
}

# Health thresholds
THRESHOLDS = {
    'cpu_warning': 60,
    'cpu_critical': 85,
    'mem_warning': 70,
    'mem_critical': 90,
    'load_warning': 2.0,
    'load_critical': 4.0,
    'swap_warning': 20,
    'swap_critical': 50,
    'iowait_warning': 15,
    'iowait_critical': 30,
    'steal_warning': 5,
    'steal_critical': 15,
    'disk_warning': 80,
    'disk_critical': 90,
    'fd_warning': 60,
    'fd_critical': 80,
}

def get_health_status(value, warning_threshold, critical_threshold):
    """Get health status and color based on value."""
    if value >= critical_threshold:
        return 'critical', COLORS['status_critical'], '🔴'
    elif value >= warning_threshold:
        return 'warning', COLORS['status_warning'], '🟡'
    else:
        return 'good', COLORS['status_good'], '🟢'

def create_gradient_defs():
    """Create SVG gradient definitions for reuse."""
    return '''<defs>
    <linearGradient id="cpuGradient" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#60a5fa;stop-opacity:0.8" />
      <stop offset="100%" style="stop-color:#3b82f6;stop-opacity:0.3" />
    </linearGradient>
    <linearGradient id="memGradient" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#a78bfa;stop-opacity:0.8" />
      <stop offset="100%" style="stop-color:#8b5cf6;stop-opacity:0.3" />
    </linearGradient>
    <linearGradient id="successGradient" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#4ade80;stop-opacity:0.8" />
      <stop offset="100%" style="stop-color:#22c55e;stop-opacity:0.3" />
    </linearGradient>
    <linearGradient id="warningGradient" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#fde047;stop-opacity:0.8" />
      <stop offset="100%" style="stop-color:#eab308;stop-opacity:0.3" />
    </linearGradient>
    <linearGradient id="dangerGradient" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#f87171;stop-opacity:0.8" />
      <stop offset="100%" style="stop-color:#ef4444;stop-opacity:0.3" />
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-opacity="0.15"/>
    </filter>
    <filter id="glow">
      <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
      <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>'''

def format_bytes(bytes_val, precision=1):
    """Format bytes to human readable."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.{precision}f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.{precision}f} PB"

def format_duration(seconds):
    """Format seconds to human readable duration."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"

def create_smooth_path(points):
    """Create a smooth bezier curve path from points."""
    if len(points) < 2:
        return ""
    
    path = f"M {points[0][0]} {points[0][1]}"
    
    for i in range(1, len(points)):
        x0, y0 = points[i-1]
        x1, y1 = points[i]
        
        # Control points for smooth curve
        cp1x = x0 + (x1 - x0) * 0.4
        cp1y = y0
        cp2x = x0 + (x1 - x0) * 0.6
        cp2y = y1
        
        path += f" C {cp1x} {cp1y}, {cp2x} {cp2y}, {x1} {y1}"
    
    return path

def create_line_chart_svg(data_series, width=600, height=200, title="", y_label="", show_legend=True, smooth=True):
    """
    Create a multi-line time-series chart with modern styling.
    data_series: list of {name, values, color}
    """
    if not data_series or not data_series[0]['values']:
        return f'<svg width="{width}" height="{height}"><text x="50%" y="50%" text-anchor="middle">No data</text></svg>'
    
    padding = {'top': 45, 'right': 20, 'bottom': 55, 'left': 65}
    if show_legend:
        padding['right'] = 130
    
    chart_width = width - padding['left'] - padding['right']
    chart_height = height - padding['top'] - padding['bottom']
    
    # Find data range
    all_values = [v for series in data_series for v in series['values'] if v is not None]
    if not all_values:
        return f'<svg width="{width}" height="{height}"><text x="50%" y="50%" text-anchor="middle">No data</text></svg>'
    
    min_val = min(0, min(all_values))
    max_val = max(all_values) * 1.15  # 15% padding for visual breathing room
    if max_val == min_val:
        max_val = min_val + 1
    
    num_points = len(data_series[0]['values'])
    
    def x_pos(i):
        return padding['left'] + (i / max(1, num_points - 1)) * chart_width
    
    def y_pos(v):
        if v is None:
            return None
        return padding['top'] + chart_height - ((v - min_val) / (max_val - min_val)) * chart_height
    
    # Build SVG
    svg_parts = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">']
    svg_parts.append(create_gradient_defs())
    
    # Background with subtle gradient
    svg_parts.append(f'<rect width="{width}" height="{height}" fill="white" rx="8"/>')
    svg_parts.append(f'<rect x="{padding["left"]}" y="{padding["top"]}" width="{chart_width}" height="{chart_height}" fill="#f8fafc" rx="4"/>')
    
    # Title with icon
    svg_parts.append(f'<text x="{width//2}" y="22" text-anchor="middle" font-size="14" font-weight="600" fill="{COLORS["dark"]}">{title}</text>')
    
    # Subtle grid lines
    num_grid_lines = 5
    for i in range(num_grid_lines + 1):
        y = padding['top'] + (i / num_grid_lines) * chart_height
        val = max_val - (i / num_grid_lines) * (max_val - min_val)
        svg_parts.append(f'<line x1="{padding["left"]}" y1="{y}" x2="{width - padding["right"]}" y2="{y}" stroke="#e2e8f0" stroke-width="1" stroke-dasharray="4,4"/>')
        svg_parts.append(f'<text x="{padding["left"] - 8}" y="{y + 4}" text-anchor="end" font-size="10" fill="{COLORS["gray"]}">{val:.1f}</text>')
    
    # Y-axis label
    svg_parts.append(f'<text x="18" y="{height//2}" text-anchor="middle" font-size="10" fill="{COLORS["gray"]}" transform="rotate(-90 18 {height//2})">{y_label}</text>')
    
    # X-axis time labels
    num_x_labels = min(6, num_points)
    for i in range(num_x_labels):
        idx = int((i / max(1, num_x_labels - 1)) * (num_points - 1))
        x = x_pos(idx)
        svg_parts.append(f'<text x="{x}" y="{height - 15}" text-anchor="middle" font-size="10" fill="{COLORS["gray"]}">{idx * 2}s</text>')
    
    # Gradient mapping
    gradient_map = {
        COLORS['cpu']: 'url(#cpuGradient)',
        COLORS['memory']: 'url(#memGradient)',
        COLORS['success']: 'url(#successGradient)',
        COLORS['load']: 'url(#warningGradient)',
    }
    
    # Plot lines with area fill
    for series in data_series:
        points = []
        for i, v in enumerate(series['values']):
            if v is not None:
                points.append((x_pos(i), y_pos(v)))
        
        if len(points) > 1:
            # Area fill with gradient
            gradient = gradient_map.get(series['color'], f'{series["color"]}')
            
            if smooth and len(points) > 2:
                # Smooth area
                area_path = f'M {points[0][0]} {padding["top"] + chart_height}'
                area_path += f' L {points[0][0]} {points[0][1]}'
                for i in range(1, len(points)):
                    x0, y0 = points[i-1]
                    x1, y1 = points[i]
                    cp1x = x0 + (x1 - x0) * 0.4
                    cp2x = x0 + (x1 - x0) * 0.6
                    area_path += f' C {cp1x} {y0}, {cp2x} {y1}, {x1} {y1}'
                area_path += f' L {points[-1][0]} {padding["top"] + chart_height} Z'
                svg_parts.append(f'<path d="{area_path}" fill="{series["color"]}" fill-opacity="0.15"/>')
                
                # Smooth line
                line_path = create_smooth_path(points)
                svg_parts.append(f'<path d="{line_path}" fill="none" stroke="{series["color"]}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>')
            else:
                # Sharp area
                area_path = f'M {points[0][0]} {padding["top"] + chart_height}'
                for x, y in points:
                    area_path += f' L {x} {y}'
                area_path += f' L {points[-1][0]} {padding["top"] + chart_height} Z'
                svg_parts.append(f'<path d="{area_path}" fill="{series["color"]}" fill-opacity="0.15"/>')
                
                # Sharp line
                line_path = f'M {points[0][0]} {points[0][1]}'
                for x, y in points[1:]:
                    line_path += f' L {x} {y}'
                svg_parts.append(f'<path d="{line_path}" fill="none" stroke="{series["color"]}" stroke-width="2.5" stroke-linecap="round"/>')
            
            # End point dot with glow effect
            last_x, last_y = points[-1]
            svg_parts.append(f'<circle cx="{last_x}" cy="{last_y}" r="5" fill="{series["color"]}" fill-opacity="0.3"/>')
            svg_parts.append(f'<circle cx="{last_x}" cy="{last_y}" r="3" fill="{series["color"]}"/>')
    
    # Legend with better styling
    if show_legend:
        legend_x = width - padding['right'] + 15
        legend_bg_height = len(data_series) * 24 + 12
        svg_parts.append(f'<rect x="{legend_x - 5}" y="{padding["top"] + 5}" width="105" height="{legend_bg_height}" fill="white" stroke="#e2e8f0" rx="6"/>')
        for i, series in enumerate(data_series):
            legend_y = padding['top'] + 22 + i * 24
            svg_parts.append(f'<circle cx="{legend_x + 8}" cy="{legend_y - 3}" r="5" fill="{series["color"]}"/>')
            svg_parts.append(f'<text x="{legend_x + 20}" y="{legend_y}" font-size="11" fill="{COLORS["dark"]}">{series["name"]}</text>')
    
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)

def create_area_chart_svg(data_series, width=600, height=180, title=""):
    """Create stacked area chart for I/O metrics."""
    return create_line_chart_svg(data_series, width, height, title, show_legend=True)

def create_gauge_svg(value, max_val=100, label="", size=120, show_trend=None):
    """Create a modern donut-style gauge with status indicator."""
    percent = min(value / max_val, 1.0) if max_val > 0 else 0
    
    # Get health status
    status, color, icon = get_health_status(value, 
        THRESHOLDS.get('cpu_warning', 60), 
        THRESHOLDS.get('cpu_critical', 85))
    
    if 'Memory' in label:
        status, color, icon = get_health_status(value, 
            THRESHOLDS.get('mem_warning', 70), 
            THRESHOLDS.get('mem_critical', 90))
    
    radius = size * 0.38
    cx, cy = size // 2, size // 2
    circumference = 2 * math.pi * radius
    dash_offset = circumference * (1 - percent)
    
    # Trend arrow
    trend_svg = ""
    if show_trend is not None:
        if show_trend > 0.5:
            trend_svg = f'<text x="{size - 15}" y="20" font-size="14" fill="{COLORS["danger"]}">↑</text>'
        elif show_trend < -0.5:
            trend_svg = f'<text x="{size - 15}" y="20" font-size="14" fill="{COLORS["success"]}">↓</text>'
        else:
            trend_svg = f'<text x="{size - 15}" y="20" font-size="12" fill="{COLORS["gray"]}">→</text>'
    
    return f'''<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <defs>
    <linearGradient id="gaugeGrad{label.replace(' ', '')}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{color};stop-opacity:0.7" />
    </linearGradient>
  </defs>
  <!-- Background ring -->
  <circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="#e2e8f0" stroke-width="12"/>
  <!-- Value ring -->
  <circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="url(#gaugeGrad{label.replace(' ', '')})" stroke-width="12"
          stroke-dasharray="{circumference}" stroke-dashoffset="{dash_offset}"
          transform="rotate(-90 {cx} {cy})" stroke-linecap="round"/>
  <!-- Center content -->
  <circle cx="{cx}" cy="{cy}" r="{radius - 18}" fill="white"/>
  <text x="{cx}" y="{cy - 2}" text-anchor="middle" font-size="20" font-weight="700" fill="{COLORS['dark']}">{value:.1f}%</text>
  <text x="{cx}" y="{cy + 14}" text-anchor="middle" font-size="9" fill="{COLORS['gray']}">{status.upper()}</text>
  <!-- Label -->
  <text x="{cx}" y="{size - 8}" text-anchor="middle" font-size="11" font-weight="500" fill="{COLORS['dark']}">{label}</text>
  {trend_svg}
</svg>'''

def create_sparkline_svg(values, width=120, height=30, color=COLORS['primary']):
    """Create a mini sparkline chart."""
    if not values:
        return f'<svg width="{width}" height="{height}"></svg>'
    
    min_val = min(values)
    max_val = max(values)
    if max_val == min_val:
        max_val = min_val + 1
    
    points = []
    for i, v in enumerate(values):
        x = (i / max(1, len(values) - 1)) * width
        y = height - ((v - min_val) / (max_val - min_val)) * (height - 4) - 2
        points.append(f'{x},{y}')
    
    path = 'M ' + ' L '.join(points)
    
    return f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <path d="{path}" fill="none" stroke="{color}" stroke-width="1.5"/>
  <circle cx="{width}" cy="{points[-1].split(',')[1]}" r="2" fill="{color}"/>
</svg>'''

def create_bar_chart_svg(data, width=400, height=200, title="", horizontal=True):
    """Create a modern bar chart with rounded corners and gradients."""
    if not data:
        return ""
    
    padding = {'top': 40, 'right': 60, 'bottom': 25, 'left': 145}
    chart_height = height - padding['top'] - padding['bottom']
    chart_width = width - padding['left'] - padding['right']
    
    max_val = max(d['value'] for d in data) if data else 1
    bar_height = min(28, (chart_height - 10) / len(data))
    gap = 6
    
    svg_parts = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">']
    svg_parts.append(create_gradient_defs())
    svg_parts.append(f'<rect width="{width}" height="{height}" fill="white" rx="8"/>')
    svg_parts.append(f'<text x="{width//2}" y="24" text-anchor="middle" font-size="13" font-weight="600" fill="{COLORS["dark"]}">{title}</text>')
    
    for i, item in enumerate(data):
        y = padding['top'] + i * (bar_height + gap)
        bar_width = (item['value'] / max_val) * chart_width if max_val > 0 else 0
        color = item.get('color', COLORS['primary'])
        
        # Truncate label
        label = item['label'][:18] + ('…' if len(item['label']) > 18 else '')
        
        # Background bar
        svg_parts.append(f'<rect x="{padding["left"]}" y="{y}" width="{chart_width}" height="{bar_height}" fill="#f1f5f9" rx="4"/>')
        
        # Value bar with gradient effect
        svg_parts.append(f'<rect x="{padding["left"]}" y="{y}" width="{bar_width}" height="{bar_height}" fill="{color}" rx="4"/>')
        svg_parts.append(f'<rect x="{padding["left"]}" y="{y}" width="{bar_width}" height="{bar_height * 0.4}" fill="white" fill-opacity="0.2" rx="4"/>')
        
        svg_parts.append(f'<text x="{padding["left"] - 8}" y="{y + bar_height/2 + 4}" text-anchor="end" font-size="11" fill="{COLORS["dark"]}">{label}</text>')
        svg_parts.append(f'<text x="{padding["left"] + bar_width + 8}" y="{y + bar_height/2 + 4}" font-size="11" font-weight="500" fill="{COLORS["gray"]}">{item["value"]:.1f}%</text>')
    
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)

def create_stats_card_svg(stats, width=300, height=130, title="", accent_color=None):
    """Create a modern statistics card with accent color bar."""
    accent = accent_color or COLORS['primary']
    
    svg_parts = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">']
    svg_parts.append(create_gradient_defs())
    
    # Card background with shadow effect
    svg_parts.append(f'<rect x="2" y="2" width="{width-4}" height="{height-4}" fill="white" stroke="#e2e8f0" stroke-width="1" rx="10" filter="url(#shadow)"/>')
    
    # Accent bar at top
    svg_parts.append(f'<rect x="2" y="2" width="{width-4}" height="4" fill="{accent}" rx="2"/>')
    
    # Title
    svg_parts.append(f'<text x="16" y="28" font-size="12" font-weight="600" fill="{COLORS["dark"]}">{title}</text>')
    
    col_width = (width - 20) // 2
    for i, stat in enumerate(stats[:4]):
        x = 16 + (i % 2) * col_width
        y = 55 + (i // 2) * 38
        svg_parts.append(f'<text x="{x}" y="{y}" font-size="20" font-weight="700" fill="{stat.get("color", COLORS["primary"])}">{stat["value"]}</text>')
        svg_parts.append(f'<text x="{x}" y="{y + 14}" font-size="9" fill="{COLORS["gray"]}">{stat["label"]}</text>')
    
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)

def create_heatmap_row_svg(values, labels, width=500, height=50, title="", color_scale='blue'):
    """Create a horizontal heatmap row."""
    if not values:
        return ""
    
    cell_width = min(60, (width - 100) // len(values))
    total_cells_width = cell_width * len(values)
    start_x = (width - total_cells_width) // 2
    
    max_val = max(values) if values else 1
    
    svg_parts = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">']
    
    if title:
        svg_parts.append(f'<text x="{width//2}" y="15" text-anchor="middle" font-size="11" font-weight="bold" fill="{COLORS["dark"]}">{title}</text>')
    
    for i, (val, label) in enumerate(zip(values, labels)):
        x = start_x + i * cell_width
        intensity = val / max_val if max_val > 0 else 0
        
        # Blue to red color scale
        if intensity < 0.5:
            r = int(intensity * 2 * 200)
            g = int(100 + intensity * 100)
            b = 255
        else:
            r = 255
            g = int((1 - intensity) * 200)
            b = int((1 - intensity) * 255)
        
        color = f'rgb({r},{g},{b})'
        text_color = 'white' if intensity > 0.3 else COLORS['dark']
        
        svg_parts.append(f'<rect x="{x}" y="22" width="{cell_width - 3}" height="{cell_width - 3}" fill="{color}" rx="4"/>')
        svg_parts.append(f'<text x="{x + cell_width//2 - 1}" y="{22 + cell_width//2 + 3}" text-anchor="middle" font-size="11" font-weight="bold" fill="{text_color}">{val:.1f}</text>')
        svg_parts.append(f'<text x="{x + cell_width//2 - 1}" y="{height - 3}" text-anchor="middle" font-size="8" fill="{COLORS["gray"]}">{label}</text>')
    
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)

# Step colors for consistent coloring - modern vibrant palette
STEP_COLORS = [
    '#3b82f6',  # blue
    '#8b5cf6',  # purple  
    '#10b981',  # emerald
    '#f59e0b',  # amber
    '#06b6d4',  # cyan
    '#ec4899',  # pink
    '#84cc16',  # lime
    '#14b8a6',  # teal
    '#f43f5e',  # rose
    '#6366f1',  # indigo
]

def create_gantt_chart_svg(steps, total_duration, width=680, height=None):
    """Create a modern Gantt-style chart showing step timeline with icons."""
    if not steps:
        return ""
    
    bar_height = 32
    gap = 8
    padding = {'top': 50, 'right': 60, 'bottom': 35, 'left': 170}
    
    if height is None:
        height = padding['top'] + len(steps) * (bar_height + gap) + padding['bottom']
    
    chart_width = width - padding['left'] - padding['right']
    
    svg_parts = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">']
    svg_parts.append(create_gradient_defs())
    svg_parts.append(f'<rect width="{width}" height="{height}" fill="white" rx="8"/>')
    svg_parts.append(f'<text x="{width//2}" y="25" text-anchor="middle" font-size="14" font-weight="600" fill="{COLORS["dark"]}">⏱️ Step Timeline</text>')
    
    # Time axis background
    svg_parts.append(f'<rect x="{padding["left"]}" y="{padding["top"] - 5}" width="{chart_width}" height="{height - padding["top"] - padding["bottom"] + 10}" fill="#f8fafc" rx="4"/>')
    
    # Time axis
    num_ticks = 5
    for i in range(num_ticks + 1):
        x = padding['left'] + (i / num_ticks) * chart_width
        time_val = (i / num_ticks) * total_duration
        svg_parts.append(f'<line x1="{x}" y1="{padding["top"] - 5}" x2="{x}" y2="{height - padding["bottom"]}" stroke="#e2e8f0" stroke-width="1" stroke-dasharray="4,4"/>')
        svg_parts.append(f'<text x="{x}" y="{height - 12}" text-anchor="middle" font-size="10" fill="{COLORS["gray"]}">{format_duration(time_val)}</text>')
    
    # Step bars with modern styling
    for i, step in enumerate(steps):
        y = padding['top'] + i * (bar_height + gap)
        start_pct = step.get('start_offset', 0) / total_duration if total_duration > 0 else 0
        duration_pct = step.get('duration', 0) / total_duration if total_duration > 0 else 0
        
        x_start = padding['left'] + start_pct * chart_width
        bar_width = max(duration_pct * chart_width, 8)  # min width
        
        color = STEP_COLORS[i % len(STEP_COLORS)]
        
        # Step name with number badge
        name = step['name'][:22] + ('…' if len(step['name']) > 22 else '')
        svg_parts.append(f'<circle cx="{padding["left"] - 155}" cy="{y + bar_height/2}" r="10" fill="{color}"/>')
        svg_parts.append(f'<text x="{padding["left"] - 155}" y="{y + bar_height/2 + 4}" text-anchor="middle" font-size="10" font-weight="600" fill="white">{i + 1}</text>')
        svg_parts.append(f'<text x="{padding["left"] - 138}" y="{y + bar_height/2 + 4}" font-size="11" fill="{COLORS["dark"]}">{name}</text>')
        
        # Bar with rounded corners and highlight
        svg_parts.append(f'<rect x="{x_start}" y="{y}" width="{bar_width}" height="{bar_height}" fill="{color}" rx="6"/>')
        svg_parts.append(f'<rect x="{x_start}" y="{y}" width="{bar_width}" height="{bar_height * 0.35}" fill="white" fill-opacity="0.25" rx="6"/>')
        
        # Duration label
        duration_text = format_duration(step.get('duration', 0))
        svg_parts.append(f'<text x="{x_start + bar_width + 8}" y="{y + bar_height/2 + 4}" font-size="10" font-weight="500" fill="{COLORS["gray"]}">{duration_text}</text>')
    
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)

def create_step_cpu_chart_svg(steps, width=680, height=220):
    """Create a modern grouped bar chart showing resource usage by step."""
    if not steps:
        return ""
    
    padding = {'top': 50, 'right': 25, 'bottom': 60, 'left': 65}
    chart_width = width - padding['left'] - padding['right']
    chart_height = height - padding['top'] - padding['bottom']
    
    # Calculate max values
    max_cpu = max((s.get('max_cpu', 0) for s in steps), default=1)
    max_mem = max((s.get('max_mem', 0) for s in steps), default=1)
    max_val = max(max_cpu, max_mem, 1) * 1.2
    
    svg_parts = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">']
    svg_parts.append(create_gradient_defs())
    svg_parts.append(f'<rect width="{width}" height="{height}" fill="white" rx="8"/>')
    svg_parts.append(f'<text x="{width//2}" y="25" text-anchor="middle" font-size="14" font-weight="600" fill="{COLORS["dark"]}">📊 Resource Usage by Step</text>')
    
    # Chart background
    svg_parts.append(f'<rect x="{padding["left"]}" y="{padding["top"]}" width="{chart_width}" height="{chart_height}" fill="#f8fafc" rx="4"/>')
    
    # Grid
    for i in range(5):
        y = padding['top'] + (i / 4) * chart_height
        val = max_val * (1 - i/4)
        svg_parts.append(f'<line x1="{padding["left"]}" y1="{y}" x2="{width - padding["right"]}" y2="{y}" stroke="#e2e8f0" stroke-width="1" stroke-dasharray="4,4"/>')
        svg_parts.append(f'<text x="{padding["left"] - 8}" y="{y + 4}" text-anchor="end" font-size="10" fill="{COLORS["gray"]}">{val:.0f}%</text>')
    
    # Grouped bars for each step - using consistent CPU (blue) and Memory (purple) colors
    group_width = chart_width / len(steps)
    bar_width = group_width * 0.35
    
    for i, step in enumerate(steps):
        group_x = padding['left'] + i * group_width + group_width * 0.15
        
        # CPU bar (blue)
        cpu_height = (step.get('avg_cpu', 0) / max_val) * chart_height
        cpu_y = padding['top'] + chart_height - cpu_height
        svg_parts.append(f'<rect x="{group_x}" y="{cpu_y}" width="{bar_width}" height="{cpu_height}" fill="{COLORS["cpu"]}" rx="4"/>')
        svg_parts.append(f'<rect x="{group_x}" y="{cpu_y}" width="{bar_width}" height="{min(cpu_height, 8)}" fill="white" fill-opacity="0.3" rx="4"/>')
        
        # Memory bar (purple)
        mem_height = (step.get('avg_mem', 0) / max_val) * chart_height
        mem_y = padding['top'] + chart_height - mem_height
        svg_parts.append(f'<rect x="{group_x + bar_width + 4}" y="{mem_y}" width="{bar_width}" height="{mem_height}" fill="{COLORS["memory"]}" rx="4"/>')
        svg_parts.append(f'<rect x="{group_x + bar_width + 4}" y="{mem_y}" width="{bar_width}" height="{min(mem_height, 8)}" fill="white" fill-opacity="0.3" rx="4"/>')
        
        # Step number badge below bars
        badge_x = group_x + bar_width
        svg_parts.append(f'<circle cx="{badge_x}" cy="{height - 38}" r="9" fill="{STEP_COLORS[i % len(STEP_COLORS)]}"/>')
        svg_parts.append(f'<text x="{badge_x}" y="{height - 34}" text-anchor="middle" font-size="9" font-weight="600" fill="white">{i + 1}</text>')
        
        # Step label
        name = step['name'][:10] + ('..' if len(step['name']) > 10 else '')
        label_x = group_x + bar_width
        svg_parts.append(f'<text x="{label_x}" y="{height - 18}" text-anchor="middle" font-size="8" fill="{COLORS["dark"]}">{name}</text>')
    
    # Legend
    legend_x = width - 120
    svg_parts.append(f'<rect x="{legend_x - 8}" y="35" width="115" height="50" fill="white" stroke="#e2e8f0" rx="6"/>')
    svg_parts.append(f'<rect x="{legend_x}" y="45" width="14" height="14" fill="{COLORS["cpu"]}" rx="3"/>')
    svg_parts.append(f'<text x="{legend_x + 20}" y="56" font-size="10" fill="{COLORS["dark"]}">CPU Usage</text>')
    svg_parts.append(f'<rect x="{legend_x}" y="65" width="14" height="14" fill="{COLORS["memory"]}" rx="3"/>')
    svg_parts.append(f'<text x="{legend_x + 20}" y="76" font-size="10" fill="{COLORS["dark"]}">Memory Usage</text>')
    
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)

def create_step_comparison_table(steps):
    """Create an enhanced markdown table comparing step metrics with visual indicators."""
    if not steps:
        return ""
    
    # Find max values for comparison
    max_cpu = max(s.get('avg_cpu', 0) for s in steps) if steps else 1
    max_mem = max(s.get('avg_mem', 0) for s in steps) if steps else 1
    max_dur = max(s.get('duration', 0) for s in steps) if steps else 1
    
    rows = [
        "| # | Step | Duration | Avg CPU | Peak CPU | Avg Mem | Peak Mem | Intensity |",
        "|:-:|------|:--------:|:-------:|:--------:|:-------:|:--------:|:---------:|"
    ]
    
    for i, step in enumerate(steps):
        name = step['name'][:28] + ('…' if len(step['name']) > 28 else '')
        duration = format_duration(step.get('duration', 0))
        avg_cpu = step.get('avg_cpu', 0)
        max_cpu_val = step.get('max_cpu', 0)
        avg_mem = step.get('avg_mem', 0)
        max_mem_val = step.get('max_mem', 0)
        
        # Calculate intensity score (combined resource usage)
        intensity = (avg_cpu / max(max_cpu, 1) + avg_mem / max(max_mem, 1)) / 2
        
        # Visual intensity bar using unicode blocks
        bar_length = int(intensity * 5)
        intensity_bar = '█' * bar_length + '░' * (5 - bar_length)
        
        # Color-coded indicators
        cpu_indicator = '🔴' if avg_cpu > 70 else ('🟡' if avg_cpu > 40 else '🟢')
        mem_indicator = '🔴' if avg_mem > 80 else ('🟡' if avg_mem > 60 else '🟢')
        
        rows.append(f"| {i+1} | {name} | {duration} | {cpu_indicator} {avg_cpu:.1f}% | {max_cpu_val:.1f}% | {mem_indicator} {avg_mem:.1f}% | {max_mem_val:.1f}% | {intensity_bar} |")
    
    return '\n'.join(rows)

def analyze_steps(data):
    """Analyze step data and calculate per-step metrics."""
    steps = data.get('steps', [])
    samples = data.get('samples', [])
    start_time = data.get('start_time', 0)
    
    if not steps or not samples:
        return []
    
    analyzed_steps = []
    
    for i, step in enumerate(steps):
        step_start = step.get('start_time', start_time)
        step_end = step.get('end_time', data.get('end_time', step_start))
        
        # Find samples within this step's time range
        step_samples = [
            s for s in samples 
            if step_start <= s['timestamp'] <= step_end
        ]
        
        if step_samples:
            cpu_values = [s['cpu_percent'] for s in step_samples]
            mem_values = [s['memory']['percent'] for s in step_samples]
            
            analyzed_step = {
                'name': step['name'],
                'start_time': step_start,
                'end_time': step_end,
                'start_offset': step_start - start_time,
                'duration': step_end - step_start,
                'sample_count': len(step_samples),
                'avg_cpu': sum(cpu_values) / len(cpu_values),
                'max_cpu': max(cpu_values),
                'min_cpu': min(cpu_values),
                'avg_mem': sum(mem_values) / len(mem_values),
                'max_mem': max(mem_values),
                'min_mem': min(mem_values),
            }
        else:
            analyzed_step = {
                'name': step['name'],
                'start_time': step_start,
                'end_time': step_end,
                'start_offset': step_start - start_time,
                'duration': step_end - step_start,
                'sample_count': 0,
                'avg_cpu': 0, 'max_cpu': 0, 'min_cpu': 0,
                'avg_mem': 0, 'max_mem': 0, 'min_mem': 0,
            }
        
        analyzed_steps.append(analyzed_step)
    
    return analyzed_steps

def generate_steps_section(data):
    """Generate the per-step analysis section of the report with insights and recommendations."""
    analyzed_steps = analyze_steps(data)
    
    if not analyzed_steps:
        return ""
    
    duration = data.get('duration', 0)
    
    # Create visualizations
    gantt_chart = create_gantt_chart_svg(analyzed_steps, duration)
    step_chart = create_step_cpu_chart_svg(analyzed_steps)
    step_table = create_step_comparison_table(analyzed_steps)
    
    # Calculate insights
    heaviest_cpu = max(analyzed_steps, key=lambda s: s['avg_cpu'])
    heaviest_mem = max(analyzed_steps, key=lambda s: s['avg_mem'])
    longest_step = max(analyzed_steps, key=lambda s: s['duration'])
    
    # Calculate total workflow metrics
    total_cpu_time = sum(s['avg_cpu'] * s['duration'] for s in analyzed_steps)
    avg_parallelism = total_cpu_time / duration if duration > 0 else 0
    
    # Generate recommendations
    recommendations = []
    
    if heaviest_cpu['avg_cpu'] > 60:
        recommendations.append(f"💡 **{heaviest_cpu['name'][:25]}** uses high CPU ({heaviest_cpu['avg_cpu']:.1f}%). Consider caching or parallelizing.")
    
    if longest_step['duration'] > duration * 0.4:
        recommendations.append(f"⏰ **{longest_step['name'][:25]}** takes {longest_step['duration']/duration*100:.0f}% of total time. Consider splitting or optimizing.")
    
    if heaviest_mem['avg_mem'] > 70:
        recommendations.append(f"💾 **{heaviest_mem['name'][:25]}** has high memory usage ({heaviest_mem['avg_mem']:.1f}%). Monitor for OOM risks.")
    
    if not recommendations:
        recommendations.append("✅ All steps are within normal resource usage thresholds.")
    
    recommendations_text = '\n'.join([f"- {r}" for r in recommendations])
    
    section = f'''
---

## 📋 Per-Step Analysis

<table>
<tr>
<td>

### 📊 Summary
| Metric | Value |
|--------|-------|
| **Steps Tracked** | {len(analyzed_steps)} |
| **Total Duration** | {format_duration(duration)} |
| **Longest Step** | {longest_step['name'][:20]} ({format_duration(longest_step['duration'])}) |
| **Heaviest CPU** | {heaviest_cpu['name'][:20]} ({heaviest_cpu['avg_cpu']:.1f}%) |
| **Heaviest Memory** | {heaviest_mem['name'][:20]} ({heaviest_mem['avg_mem']:.1f}%) |

</td>
</tr>
</table>

### ⏱️ Step Timeline

{gantt_chart}

### 📈 Resource Comparison

{step_chart}

### 📋 Detailed Metrics

{step_table}

### 💡 Insights & Recommendations

{recommendations_text}

<details>
<summary>🔍 Per-Step Resource Breakdown</summary>

| Step | 🔥 Highest CPU | ⏳ Longest Duration | 💾 Highest Memory |
|:----:|:--------------:|:-------------------:|:-----------------:|
'''
    
    # Add ranking indicators
    for step in analyzed_steps:
        is_cpu_heavy = step == heaviest_cpu
        is_longest = step == longest_step
        is_mem_heavy = step == heaviest_mem
        
        cpu_badge = '🥇' if is_cpu_heavy else ''
        dur_badge = '🥇' if is_longest else ''
        mem_badge = '🥇' if is_mem_heavy else ''
        
        section += f"| {step['name'][:20]} | {cpu_badge} {step['avg_cpu']:.1f}% | {dur_badge} {format_duration(step['duration'])} | {mem_badge} {step['avg_mem']:.1f}% |\n"
    
    section += '\n</details>\n'
    
    return section

def generate_report(data):
    """Generate the full visual report."""
    samples = data.get('samples', [])
    
    if not samples:
        return "## ⚠️ No telemetry data collected\n\nNo samples were recorded during the monitoring period."
    
    # Extract time series data
    timestamps = [(s['timestamp'] - data['start_time']) for s in samples]
    cpu_values = [s['cpu_percent'] for s in samples]
    mem_values = [s['memory']['percent'] for s in samples]
    load_1m = [s['load']['load_1m'] for s in samples]
    disk_read = [s['disk_io']['read_rate'] / (1024*1024) for s in samples]  # MB/s
    disk_write = [s['disk_io']['write_rate'] / (1024*1024) for s in samples]
    net_rx = [s['network_io']['rx_rate'] / (1024*1024) for s in samples]  # MB/s
    net_tx = [s['network_io']['tx_rate'] / (1024*1024) for s in samples]
    
    # Extract new metrics (with fallbacks for old data)
    iowait_values = [s.get('cpu_iowait_percent', 0) for s in samples]
    steal_values = [s.get('cpu_steal_percent', 0) for s in samples]
    ctxt_rates = [s.get('context_switches_rate', 0) for s in samples]
    swap_values = [s.get('swap', {}).get('percent', 0) for s in samples]
    thread_counts = [s.get('thread_count', 0) for s in samples]
    fd_values = [s.get('file_descriptors', {}).get('percent', 0) for s in samples]
    tcp_established = [s.get('tcp_connections', {}).get('established', 0) for s in samples]
    tcp_total = [s.get('tcp_connections', {}).get('total', 0) for s in samples]
    
    # Calculate statistics
    avg_cpu = sum(cpu_values) / len(cpu_values)
    max_cpu = max(cpu_values)
    avg_mem = sum(mem_values) / len(mem_values)
    max_mem = max(mem_values)
    total_disk_read = sum(disk_read) * data.get('interval', 2)
    total_disk_write = sum(disk_write) * data.get('interval', 2)
    total_net_rx = sum(net_rx) * data.get('interval', 2)
    total_net_tx = sum(net_tx) * data.get('interval', 2)
    
    # New metric statistics
    avg_iowait = sum(iowait_values) / len(iowait_values) if iowait_values else 0
    max_iowait = max(iowait_values) if iowait_values else 0
    avg_steal = sum(steal_values) / len(steal_values) if steal_values else 0
    max_steal = max(steal_values) if steal_values else 0
    avg_swap = sum(swap_values) / len(swap_values) if swap_values else 0
    max_swap = max(swap_values) if swap_values else 0
    avg_ctxt = sum(ctxt_rates) / len(ctxt_rates) if ctxt_rates else 0
    max_ctxt = max(ctxt_rates) if ctxt_rates else 0
    avg_threads = sum(thread_counts) / len(thread_counts) if thread_counts else 0
    max_threads = max(thread_counts) if thread_counts else 0
    avg_fd = sum(fd_values) / len(fd_values) if fd_values else 0
    max_fd = max(fd_values) if fd_values else 0
    avg_tcp = sum(tcp_established) / len(tcp_established) if tcp_established else 0
    max_tcp = max(tcp_total) if tcp_total else 0
    
    duration = data.get('duration', 0)
    
    # Get context
    ctx = data.get('github_context', {})
    initial = data.get('initial_snapshot', {})
    final = data.get('final_snapshot', {})
    
    # Create visualizations
    cpu_mem_chart = create_line_chart_svg([
        {'name': 'CPU %', 'values': cpu_values, 'color': COLORS['cpu']},
        {'name': 'Memory %', 'values': mem_values, 'color': COLORS['memory']}
    ], width=650, height=200, title="CPU & Memory Usage Over Time", y_label="Percent")
    
    load_chart = create_line_chart_svg([
        {'name': 'Load 1m', 'values': load_1m, 'color': COLORS['load']}
    ], width=650, height=160, title="System Load Average", y_label="Load", show_legend=False)
    
    io_chart = create_line_chart_svg([
        {'name': 'Disk Read', 'values': disk_read, 'color': COLORS['disk_read']},
        {'name': 'Disk Write', 'values': disk_write, 'color': COLORS['disk_write']},
        {'name': 'Net RX', 'values': net_rx, 'color': COLORS['net_rx']},
        {'name': 'Net TX', 'values': net_tx, 'color': COLORS['net_tx']}
    ], width=650, height=200, title="I/O Activity (MB/s)", y_label="MB/s")
    
    # Gauges for current/final state
    final_cpu = cpu_values[-1] if cpu_values else 0
    final_mem = mem_values[-1] if mem_values else 0
    cpu_gauge = create_gauge_svg(final_cpu, 100, "CPU Now")
    mem_gauge = create_gauge_svg(final_mem, 100, "Memory Now")
    
    # Top processes bar chart
    top_procs = final.get('processes', initial.get('processes', {}))
    proc_data = []
    for p in top_procs.get('by_cpu', [])[:7]:
        cmd = p['command'].split('/')[-1].split()[0][:20]
        proc_data.append({'label': cmd, 'value': p['cpu'], 'color': COLORS['cpu']})
    proc_chart = create_bar_chart_svg(proc_data, width=400, height=220, title="Top Processes by CPU")
    
    mem_proc_data = []
    for p in top_procs.get('by_mem', [])[:7]:
        cmd = p['command'].split('/')[-1].split()[0][:20]
        mem_proc_data.append({'label': cmd, 'value': p['mem'], 'color': COLORS['memory']})
    mem_proc_chart = create_bar_chart_svg(mem_proc_data, width=400, height=220, title="Top Processes by Memory")
    
    # Load heatmap
    final_load = samples[-1]['load'] if samples else {}
    load_heatmap = create_heatmap_row_svg(
        [final_load.get('load_1m', 0), final_load.get('load_5m', 0), final_load.get('load_15m', 0)],
        ['1 min', '5 min', '15 min'],
        width=300, height=80, title="Load Average"
    )
    
    # Stats cards with accent colors
    cpu_stats = create_stats_card_svg([
        {'value': f'{avg_cpu:.1f}%', 'label': 'Average', 'color': COLORS['cpu']},
        {'value': f'{max_cpu:.1f}%', 'label': 'Peak', 'color': COLORS['danger']},
        {'value': f'{final_cpu:.1f}%', 'label': 'Current', 'color': COLORS['success']},
        {'value': str(initial.get('cpu_count', 'N/A')), 'label': 'Cores', 'color': COLORS['dark']}
    ], title="📊 CPU Statistics", accent_color=COLORS['cpu'])
    
    mem_stats = create_stats_card_svg([
        {'value': f'{avg_mem:.1f}%', 'label': 'Average', 'color': COLORS['memory']},
        {'value': f'{max_mem:.1f}%', 'label': 'Peak', 'color': COLORS['danger']},
        {'value': f'{final_mem:.1f}%', 'label': 'Current', 'color': COLORS['success']},
        {'value': f'{initial.get("memory", {}).get("total_mb", 0) / 1024:.1f}G', 'label': 'Total', 'color': COLORS['dark']}
    ], title="💾 Memory Statistics", accent_color=COLORS['memory'])
    
    io_stats = create_stats_card_svg([
        {'value': format_bytes(total_disk_read * 1024 * 1024), 'label': 'Disk Read', 'color': COLORS['disk_read']},
        {'value': format_bytes(total_disk_write * 1024 * 1024), 'label': 'Disk Write', 'color': COLORS['disk_write']},
        {'value': format_bytes(total_net_rx * 1024 * 1024), 'label': 'Net RX', 'color': COLORS['net_rx']},
        {'value': format_bytes(total_net_tx * 1024 * 1024), 'label': 'Net TX', 'color': COLORS['net_tx']}
    ], title="📡 I/O Totals", accent_color=COLORS['info'])
    
    # Calculate overall health status
    cpu_status, cpu_color, cpu_icon = get_health_status(max_cpu, THRESHOLDS['cpu_warning'], THRESHOLDS['cpu_critical'])
    mem_status, mem_color, mem_icon = get_health_status(max_mem, THRESHOLDS['mem_warning'], THRESHOLDS['mem_critical'])
    load_status, load_color, load_icon = get_health_status(max(load_1m), THRESHOLDS['load_warning'], THRESHOLDS['load_critical'])
    
    # New metric health status
    iowait_status, iowait_color, iowait_icon = get_health_status(max_iowait, THRESHOLDS['iowait_warning'], THRESHOLDS['iowait_critical'])
    steal_status, steal_color, steal_icon = get_health_status(max_steal, THRESHOLDS['steal_warning'], THRESHOLDS['steal_critical'])
    swap_status, swap_color, swap_icon = get_health_status(max_swap, THRESHOLDS['swap_warning'], THRESHOLDS['swap_critical'])
    
    # Get disk space info
    final_disk_space = samples[-1].get('disk_space', {}) if samples else {}
    disk_space_pct = final_disk_space.get('percent', 0)
    disk_status, disk_color, disk_icon = get_health_status(disk_space_pct, THRESHOLDS['disk_warning'], THRESHOLDS['disk_critical'])
    
    # Get file descriptor info
    final_fd = samples[-1].get('file_descriptors', {}) if samples else {}
    fd_pct = final_fd.get('percent', 0)
    fd_status, fd_color, fd_icon = get_health_status(fd_pct, THRESHOLDS['fd_warning'], THRESHOLDS['fd_critical'])
    
    # Overall health (worst of all)
    status_priority = {'critical': 3, 'warning': 2, 'good': 1}
    all_statuses = [cpu_status, mem_status, load_status, iowait_status, steal_status, swap_status]
    overall = max(all_statuses, key=lambda s: status_priority[s])
    overall_icon = {'critical': '🔴', 'warning': '🟡', 'good': '🟢'}[overall]
    overall_text = {'critical': 'Critical', 'warning': 'Warning', 'good': 'Healthy'}[overall]
    
    # Create I/O Wait & Steal chart if we have data
    iowait_steal_chart = ""
    if max_iowait > 0 or max_steal > 0:
        iowait_steal_chart = create_line_chart_svg([
            {'name': 'I/O Wait %', 'values': iowait_values, 'color': COLORS['warning']},
            {'name': 'CPU Steal %', 'values': steal_values, 'color': COLORS['danger']}
        ], width=650, height=160, title="I/O Wait & CPU Steal Time", y_label="Percent")
    
    # Create swap chart if we have swap usage
    swap_chart = ""
    if max_swap > 0:
        swap_chart = create_line_chart_svg([
            {'name': 'Swap %', 'values': swap_values, 'color': COLORS['secondary']}
        ], width=650, height=140, title="Swap Usage", y_label="Percent", show_legend=False)
    
    # Create context switches chart
    ctxt_chart = ""
    if max_ctxt > 0:
        ctxt_chart = create_line_chart_svg([
            {'name': 'Context Switches/s', 'values': ctxt_rates, 'color': COLORS['info']}
        ], width=650, height=140, title="Context Switches (per second)", y_label="CS/s", show_legend=False)
    
    # Get TCP connection info
    final_tcp = samples[-1].get('tcp_connections', {}) if samples else {}
    
    # Build report with modern header
    report = f'''# 🖥️ Runner Telemetry Dashboard

<table>
<tr>
<td width="70%">

### 📊 Executive Summary

| Metric | Status | Value |
|--------|:------:|-------|
| **Overall Health** | {overall_icon} | **{overall_text}** |
| **CPU Usage** | {cpu_icon} | Peak: {max_cpu:.1f}% / Avg: {avg_cpu:.1f}% |
| **Memory Usage** | {mem_icon} | Peak: {max_mem:.1f}% / Avg: {avg_mem:.1f}% |
| **System Load** | {load_icon} | 1m: {final_load.get('load_1m', 0):.2f} / 5m: {final_load.get('load_5m', 0):.2f} |
| **I/O Wait** | {iowait_icon} | Peak: {max_iowait:.1f}% / Avg: {avg_iowait:.1f}% |
| **CPU Steal** | {steal_icon} | Peak: {max_steal:.1f}% / Avg: {avg_steal:.1f}% |
| **Swap Usage** | {swap_icon} | Peak: {max_swap:.1f}% / Avg: {avg_swap:.1f}% |
| **Duration** | ⏱️ | {format_duration(duration)} ({len(samples)} samples) |

</td>
<td width="30%">

{cpu_gauge}

</td>
</tr>
</table>

---

## 📈 Resource Usage Over Time

{cpu_mem_chart}

---

## ⚡ Current Status & Statistics

<table>
<tr>
<td>

{mem_gauge}

</td>
<td>

{load_heatmap}

</td>
</tr>
</table>

<table>
<tr>
<td>

{cpu_stats}

</td>
<td>

{mem_stats}

</td>
<td>

{io_stats}

</td>
</tr>
</table>

---

## 📊 System Load

{load_chart}

---

## 💿 Disk & Network I/O

{io_chart}

---

## � System Resources

### Disk Space & File Descriptors

| Resource | Status | Usage | Details |
|----------|:------:|------:|---------|
| **Disk Space** | {disk_icon} | {disk_space_pct:.1f}% | {final_disk_space.get('used_gb', 0):.1f} GB / {final_disk_space.get('total_gb', 0):.1f} GB ({final_disk_space.get('available_gb', 0):.1f} GB free) |
| **File Descriptors** | {fd_icon} | {fd_pct:.1f}% | {final_fd.get('allocated', 0):,} / {final_fd.get('max', 0):,} |
| **Threads** | ⚙️ | - | Avg: {avg_threads:.0f} / Peak: {max_threads:.0f} |
| **TCP Connections** | 🔌 | - | Total: {final_tcp.get('total', 0)} (Established: {final_tcp.get('established', 0)}, Listen: {final_tcp.get('listen', 0)}) |
| **Context Switches** | ⚡ | - | Avg: {avg_ctxt:,.0f}/s / Peak: {max_ctxt:,.0f}/s |

'''

    # Add optional charts for new metrics
    if iowait_steal_chart:
        report += f'''
### ⏳ I/O Wait & CPU Steal

{iowait_steal_chart}

> **I/O Wait**: CPU time waiting for disk operations. High values indicate slow storage.
> **CPU Steal**: Time stolen by hypervisor for other VMs. High values indicate noisy neighbors on shared runners.

'''
    
    if swap_chart:
        report += f'''
### 🔄 Swap Usage

{swap_chart}

> ⚠️ **Swap usage detected!** This indicates memory pressure - the system is using disk as virtual memory, which significantly impacts performance.

'''
    
    if ctxt_chart:
        report += f'''
### ⚡ Context Switches

{ctxt_chart}

> High context switch rates may indicate too many competing processes or inefficient workloads.

'''
    
    report += f'''---

## �🔝 Top Processes

<table>
<tr>
<td>

{proc_chart}

</td>
<td>

{mem_proc_chart}

</td>
</tr>
</table>

---

## 🔗 Workflow Context

| Property | Value |
|----------|-------|
| 📦 Repository | `{ctx.get('repository', 'N/A')}` |
| 🔄 Workflow | `{ctx.get('workflow', 'N/A')}` |
| 🎯 Job | `{ctx.get('job', 'N/A')}` |
| 🔢 Run | `#{ctx.get('run_number', 'N/A')}` (ID: {ctx.get('run_id', 'N/A')}) |
| 👤 Actor | `{ctx.get('actor', 'N/A')}` |
| 🖥️ Runner | `{ctx.get('runner_os', 'N/A')}` ({ctx.get('runner_name', 'N/A')}) |
| ⏱️ Started | `{data.get('start_datetime', 'N/A')}` |
| 🏁 Ended | `{data.get('end_datetime', 'N/A')}` |

---

<details>
<summary>📋 Raw Statistics (JSON)</summary>

```json
{{
  "duration_seconds": {duration:.2f},
  "samples_collected": {len(samples)},
  "cpu": {{"average": {avg_cpu:.2f}, "max": {max_cpu:.2f}}},
  "memory": {{"average": {avg_mem:.2f}, "max": {max_mem:.2f}}},
  "iowait": {{"average": {avg_iowait:.2f}, "max": {max_iowait:.2f}}},
  "steal": {{"average": {avg_steal:.2f}, "max": {max_steal:.2f}}},
  "swap": {{"average": {avg_swap:.2f}, "max": {max_swap:.2f}}},
  "context_switches_per_sec": {{"average": {avg_ctxt:.0f}, "max": {max_ctxt:.0f}}},
  "threads": {{"average": {avg_threads:.0f}, "max": {max_threads:.0f}}},
  "disk_space_percent": {disk_space_pct:.2f},
  "file_descriptors_percent": {fd_pct:.2f},
  "tcp_connections": {final_tcp.get('total', 0)},
  "disk_io_mb": {{"read": {total_disk_read:.2f}, "write": {total_disk_write:.2f}}},
  "network_io_mb": {{"rx": {total_net_rx:.2f}, "tx": {total_net_tx:.2f}}}
}}
```

</details>

---

<div align="center">

📊 **Runner Telemetry Action** | Generated {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | [View on GitHub](https://github.com)

</div>
'''
    
    # Add per-step analysis if steps were tracked
    steps_section = generate_steps_section(data)
    if steps_section:
        # Insert before the workflow context section
        report = report.replace('## 🔗 Workflow Context', steps_section + '\n## 🔗 Workflow Context')
    
    return report

def export_csv_files(data, output_dir):
    """Export telemetry data as CSV files for universal compatibility."""
    samples = data.get('samples', [])
    steps = data.get('steps', [])
    start_time = data.get('start_time', 0)
    
    # Export time-series samples as CSV
    if samples:
        csv_path = os.path.join(output_dir, 'telemetry-samples.csv')
        try:
            with open(csv_path, 'w') as f:
                # Header
                headers = [
                    'timestamp', 'elapsed_seconds', 'datetime',
                    'cpu_percent', 'cpu_iowait_percent', 'cpu_steal_percent',
                    'memory_percent', 'memory_used_mb', 'memory_available_mb',
                    'swap_percent', 'swap_used_mb',
                    'disk_read_rate_mbps', 'disk_write_rate_mbps',
                    'disk_space_percent', 'disk_space_used_gb', 'disk_space_available_gb',
                    'net_rx_rate_mbps', 'net_tx_rate_mbps',
                    'load_1m', 'load_5m', 'load_15m',
                    'process_count', 'thread_count',
                    'context_switches_rate',
                    'file_descriptors_allocated', 'file_descriptors_percent',
                    'tcp_total', 'tcp_established', 'tcp_time_wait'
                ]
                f.write(','.join(headers) + '\n')
                
                # Data rows
                for s in samples:
                    mem = s.get('memory', {})
                    swap = s.get('swap', {})
                    disk_io = s.get('disk_io', {})
                    disk_space = s.get('disk_space', {})
                    net_io = s.get('network_io', {})
                    load = s.get('load', {})
                    fd = s.get('file_descriptors', {})
                    tcp = s.get('tcp_connections', {})
                    
                    row = [
                        f"{s.get('timestamp', 0):.3f}",
                        f"{s.get('timestamp', 0) - start_time:.2f}",
                        s.get('datetime', ''),
                        f"{s.get('cpu_percent', 0):.2f}",
                        f"{s.get('cpu_iowait_percent', 0):.2f}",
                        f"{s.get('cpu_steal_percent', 0):.2f}",
                        f"{mem.get('percent', 0):.2f}",
                        str(mem.get('used_mb', 0)),
                        str(mem.get('available_mb', 0)),
                        f"{swap.get('percent', 0):.2f}",
                        str(swap.get('used_mb', 0)),
                        f"{disk_io.get('read_rate', 0) / (1024*1024):.3f}",
                        f"{disk_io.get('write_rate', 0) / (1024*1024):.3f}",
                        f"{disk_space.get('percent', 0):.2f}",
                        f"{disk_space.get('used_gb', 0):.2f}",
                        f"{disk_space.get('available_gb', 0):.2f}",
                        f"{net_io.get('rx_rate', 0) / (1024*1024):.3f}",
                        f"{net_io.get('tx_rate', 0) / (1024*1024):.3f}",
                        f"{load.get('load_1m', 0):.2f}",
                        f"{load.get('load_5m', 0):.2f}",
                        f"{load.get('load_15m', 0):.2f}",
                        str(s.get('process_count', 0)),
                        str(s.get('thread_count', 0)),
                        str(s.get('context_switches_rate', 0)),
                        str(fd.get('allocated', 0)),
                        f"{fd.get('percent', 0):.2f}",
                        str(tcp.get('total', 0)),
                        str(tcp.get('established', 0)),
                        str(tcp.get('time_wait', 0)),
                    ]
                    f.write(','.join(row) + '\n')
            
            print(f"✅ Time-series CSV saved to {csv_path}")
        except Exception as e:
            print(f"⚠️  Failed to save samples CSV: {e}")
    
    # Export steps as CSV
    analyzed_steps = analyze_steps(data)
    if analyzed_steps:
        steps_csv_path = os.path.join(output_dir, 'telemetry-steps.csv')
        try:
            with open(steps_csv_path, 'w') as f:
                # Header
                headers = [
                    'step_number', 'step_name', 
                    'start_time', 'end_time', 'duration_seconds',
                    'avg_cpu', 'max_cpu', 'min_cpu',
                    'avg_memory', 'max_memory', 'min_memory',
                    'sample_count'
                ]
                f.write(','.join(headers) + '\n')
                
                # Data rows
                for i, step in enumerate(analyzed_steps):
                    row = [
                        str(i + 1),
                        f'"{step.get("name", "").replace(",", ";")}"',
                        f"{step.get('start_time', 0):.3f}",
                        f"{step.get('end_time', 0):.3f}",
                        f"{step.get('duration', 0):.2f}",
                        f"{step.get('avg_cpu', 0):.2f}",
                        f"{step.get('max_cpu', 0):.2f}",
                        f"{step.get('min_cpu', 0):.2f}",
                        f"{step.get('avg_mem', 0):.2f}",
                        f"{step.get('max_mem', 0):.2f}",
                        f"{step.get('min_mem', 0):.2f}",
                        str(step.get('sample_count', 0)),
                    ]
                    f.write(','.join(row) + '\n')
            
            print(f"✅ Steps CSV saved to {steps_csv_path}")
        except Exception as e:
            print(f"⚠️  Failed to save steps CSV: {e}")
    
    # Export summary JSON (flattened, easier to consume)
    summary = create_summary_json(data, analyzed_steps)
    summary_path = os.path.join(output_dir, 'telemetry-summary.json')
    try:
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"✅ Summary JSON saved to {summary_path}")
    except Exception as e:
        print(f"⚠️  Failed to save summary JSON: {e}")


def create_summary_json(data, analyzed_steps):
    """Create a flattened summary JSON for easy consumption by dashboards."""
    samples = data.get('samples', [])
    ctx = data.get('github_context', {})
    
    # Calculate aggregates
    cpu_values = [s['cpu_percent'] for s in samples] if samples else [0]
    mem_values = [s['memory']['percent'] for s in samples] if samples else [0]
    iowait_values = [s.get('cpu_iowait_percent', 0) for s in samples] if samples else [0]
    steal_values = [s.get('cpu_steal_percent', 0) for s in samples] if samples else [0]
    swap_values = [s.get('swap', {}).get('percent', 0) for s in samples] if samples else [0]
    
    summary = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "format_version": "1.0",
            "repository": ctx.get('repository', 'N/A'),
            "workflow": ctx.get('workflow', 'N/A'),
            "job": ctx.get('job', 'N/A'),
            "run_id": ctx.get('run_id', 'N/A'),
            "run_number": ctx.get('run_number', 'N/A'),
            "actor": ctx.get('actor', 'N/A'),
            "runner_os": ctx.get('runner_os', 'N/A'),
            "runner_name": ctx.get('runner_name', 'N/A'),
        },
        "timing": {
            "start_time": data.get('start_time', 0),
            "end_time": data.get('end_time', 0),
            "duration_seconds": data.get('duration', 0),
            "start_datetime": data.get('start_datetime', ''),
            "end_datetime": data.get('end_datetime', ''),
            "sample_count": len(samples),
            "sample_interval": data.get('interval', 2),
        },
        "cpu": {
            "average_percent": round(sum(cpu_values) / len(cpu_values), 2),
            "max_percent": round(max(cpu_values), 2),
            "min_percent": round(min(cpu_values), 2),
            "core_count": data.get('initial_snapshot', {}).get('cpu_count', 0),
        },
        "memory": {
            "average_percent": round(sum(mem_values) / len(mem_values), 2),
            "max_percent": round(max(mem_values), 2),
            "min_percent": round(min(mem_values), 2),
            "total_mb": data.get('initial_snapshot', {}).get('memory', {}).get('total_mb', 0),
        },
        "iowait": {
            "average_percent": round(sum(iowait_values) / len(iowait_values), 2),
            "max_percent": round(max(iowait_values), 2),
        },
        "cpu_steal": {
            "average_percent": round(sum(steal_values) / len(steal_values), 2),
            "max_percent": round(max(steal_values), 2),
        },
        "swap": {
            "average_percent": round(sum(swap_values) / len(swap_values), 2),
            "max_percent": round(max(swap_values), 2),
            "total_mb": data.get('initial_snapshot', {}).get('swap', {}).get('total_mb', 0),
        },
        "disk_space": {
            "total_gb": samples[-1].get('disk_space', {}).get('total_gb', 0) if samples else 0,
            "used_gb": samples[-1].get('disk_space', {}).get('used_gb', 0) if samples else 0,
            "available_gb": samples[-1].get('disk_space', {}).get('available_gb', 0) if samples else 0,
            "percent_used": samples[-1].get('disk_space', {}).get('percent', 0) if samples else 0,
        },
        "steps": [
            {
                "number": i + 1,
                "name": step.get('name', ''),
                "duration_seconds": round(step.get('duration', 0), 2),
                "avg_cpu_percent": round(step.get('avg_cpu', 0), 2),
                "max_cpu_percent": round(step.get('max_cpu', 0), 2),
                "avg_memory_percent": round(step.get('avg_mem', 0), 2),
                "max_memory_percent": round(step.get('max_mem', 0), 2),
            }
            for i, step in enumerate(analyzed_steps or [])
        ],
        "health": {
            "cpu_status": "critical" if max(cpu_values) >= 85 else ("warning" if max(cpu_values) >= 60 else "good"),
            "memory_status": "critical" if max(mem_values) >= 90 else ("warning" if max(mem_values) >= 70 else "good"),
            "swap_used": max(swap_values) > 0,
            "cpu_steal_detected": max(steal_values) > 0,
        }
    }
    
    return summary


def main():
    # Load collected data
    if not os.path.exists(DATA_FILE):
        print(f"Error: No data file found at {DATA_FILE}")
        sys.exit(1)
    
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    
    report = generate_report(data)
    
    # Write to GITHUB_STEP_SUMMARY if available
    summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_file:
        with open(summary_file, 'a') as f:
            f.write(report)
        print("✅ Report written to GitHub Step Summary")
    
    # Also write to a local file
    output_dir = os.environ.get('GITHUB_WORKSPACE', '/github/workspace')
    report_path = os.path.join(output_dir, 'telemetry-report.md')
    
    try:
        with open(report_path, 'w') as f:
            f.write(report)
        print(f"✅ Report saved to {report_path}")
    except:
        with open('telemetry-report.md', 'w') as f:
            f.write(report)
        print("✅ Report saved to telemetry-report.md")
    
    # Save raw data as JSON
    try:
        json_path = os.path.join(output_dir, 'telemetry-data.json')
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Raw data saved to {json_path}")
    except:
        pass
    
    # Export CSV and summary files for external dashboards
    export_csv_files(data, output_dir)
    
    # Print summary to console
    print("\n" + "="*60)
    print(f"📊 Telemetry Summary:")
    print(f"   Duration: {format_duration(data.get('duration', 0))}")
    print(f"   Samples: {len(data.get('samples', []))}")
    if data.get('samples'):
        cpu_vals = [s['cpu_percent'] for s in data['samples']]
        mem_vals = [s['memory']['percent'] for s in data['samples']]
        print(f"   CPU: avg={sum(cpu_vals)/len(cpu_vals):.1f}%, max={max(cpu_vals):.1f}%")
        print(f"   Memory: avg={sum(mem_vals)/len(mem_vals):.1f}%, max={max(mem_vals):.1f}%")
    print("="*60)

if __name__ == '__main__':
    main()
