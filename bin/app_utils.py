from PIL import Image
import io
import numpy as np
import uuid
import pandas as pd
import os,sys
from art import tprint
from wand.image import Image as WandImage
import streamlit as st
import altair as alt
from pydantic import BaseModel

sys.path.append('..')
import apeiron.utils as U
import pytz
from datetime import datetime, timedelta

CLI_TITLE = 'Apeiron'


def svg_to_image(svg_file_path: str):
    with WandImage(filename=svg_file_path, resolution=300) as img:
        png_blob = img.make_blob('png')
        png_stream = io.BytesIO(png_blob)
        with Image.open(png_stream) as p_img:
            return p_img.copy()

def image_make_transparent(image: Image.Image, from_color: str = '000000', upper_color: str = None) -> Image.Image:
    """
    Make all pixels of the specified color transparent in the image.
    if upper_color is specified, it will make all pixels in the range from from_color to upper_color transparent.
    """
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    data = np.array(image)
    r, g, b, a = data.T
    if upper_color is not None:
        # Create a mask for the color range
        r_min = max(0, int(from_color[0:2], 16))
        r_max = min(255, int(upper_color[0:2], 16))
        g_min = max(0, int(from_color[2:4], 16))
        g_max = min(255, int(upper_color[2:4], 16))
        b_min = max(0, int(from_color[4:6], 16))
        b_max = min(255, int(upper_color[4:6], 16))

        mask = (r >= r_min) & (r <= r_max) & (g >= g_min) & (g <= g_max) & (b >= b_min) & (b <= b_max)
    else:
        mask = (r == int(from_color[0:2], 16)) & (g == int(from_color[2:4], 16)) & (b == int(from_color[4:6], 16))
    data[..., 3][mask.T] = 0
    return Image.fromarray(data, 'RGBA')


    
def get_bin_dir():
    project_dir = st.session_state['project_dir']
    return U.pjoin(project_dir, 'bin')


def load_logo(bin_dir=None):
    """
    Load the Apeiron logo image from the assets directory.
    """
    bin_dir = get_bin_dir() if bin_dir is None else bin_dir
    img_path=U.pjoin(bin_dir,'assets','apeiron.jpg')
    image = Image.open(img_path)
    return image, ''

def side_status():
    with st.sidebar:
        system = st.session_state.system
        cfg_name = system.config['name']
        exp_name = system.exp_name
        image, _ = load_logo()
        st.image(image, caption=f"Configuration: :blue[{cfg_name}] | Namespace: :blue[{exp_name}]")



def spacer(height: int = 28):
    st.markdown(f"<div style='width: 1px; height: {height}px'></div>", unsafe_allow_html=True)

def button_sb_spacer(): # to align with selectbox
    spacer(28)

def checkbox_sb_spacer(): # to align with checkbox
    spacer(36)


class PieObject(BaseModel):
    Category: str
    Value: float
    Caption: str = None  # Optional caption for the pie slice, an hover text
    # color: str = None  # Optional color for the pie slice

class PieData(BaseModel):
    data: list[PieObject]  # List of PieObject instances
    startangle: int = 0  # Default start angle for the pie chart
    title: str = None  # Optional title for the pie chart

def draw_pie(data: PieData): # [{Category: .., Value: .., caption: .., ..}]
    # Convert the dictionary to a DataFrame
    data_df = pd.DataFrame([(item.Category, item.Value, item.Caption) for item in data.data],
                          columns=['Category', 'Value', 'Caption'])


    # Calculate the percentage for each slice
    total = sum(item.Value for item in data.data)
    data_df['Percentage'] = data_df['Value'] / total * 100
    total_value = data_df['Value'].sum()
    # todo: make the category label wider
    data_df['Category'] = data_df.apply(lambda row: f"{row['Category']} ({row['Value']/total_value:.1%})", axis=1)  # Label with category and value
    data_df['Label'] = data_df['Percentage'].map('{:.1f}%'.format)  # Format percentage labels
    
    
    # Create the pie chart
    pie_chart = alt.Chart(data_df).mark_arc(innerRadius=0).encode(
        theta=alt.Theta('Value', type='quantitative'),
        color=alt.Color('Category', type='nominal'),
        tooltip=[alt.Tooltip('Category', title='Category'), 
                 alt.Tooltip('Percentage', format='.2f', title='Percentage (%)'),
                 alt.Tooltip('Caption', title='Caption', type='nominal')
                ],
    ).configure_view(
        strokeWidth=0
    ).configure_arc(
        startAngle=data.startangle * (np.pi / 180),  # Convert degrees to radians
    )

    if data.title:
        pie_chart = pie_chart.properties(title=data.title)
    
    return pie_chart


