import streamlit as st
import pandas as pd
from typing import Tuple
from huggingface_hub import login
import plotly.express as px
from IPython.display import display
from pathlib import Path
import json
from code_editor import code_editor
import streamlit_authenticator as stauth

from login import render_login
from data_import_tab import render_data_import_tab
from main_tab import render_main_tab
from info_tab import render_info_tab
from sidebar import render_sidebar

from configs import CONFIGS_FOLDER_NAME, get_cookie_config
from user_tools import load_users_dataframe, dataframe_to_config


# Load authentication configuration from Google Sheets
users_df = load_users_dataframe()
config = dataframe_to_config(users_df)

# Get cookie configuration from secrets
cookie_config = get_cookie_config()

# Create authenticator object
authenticator = stauth.Authenticate(
    config['credentials'],
    cookie_config['name'],
    cookie_config['key'],
    cookie_config['expiry_days']
)

# Ensure configs directory exists
Path(CONFIGS_FOLDER_NAME).mkdir(exist_ok=True)




# Set page configuration
st.set_page_config(
    page_title="Budget Analysis App",
    page_icon="💰",
    layout="wide"
)

# Authentication
authenticator.login(location='main')

render_login(config, authenticator)#if no user is authenticated, log stops the rest of the UI from rendering



st.title("Credit Card Categorization App")

render_sidebar(authenticator)

# Initialize session state
if 'config_key' not in st.session_state:
    st.session_state.config_key = 0

# Create tabs
info_tab, data_import_tab, main_tab = st.tabs(["ℹ️ Info", "📁 Data Import", "📊 Main"])

render_info_tab(info_tab)
render_data_import_tab(data_import_tab)
render_main_tab(main_tab)