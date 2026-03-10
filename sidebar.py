import streamlit as st


def clear_analysis_results():
    """Clear all analysis results from session state"""
    keys_to_clear = ['analysis_results', 'fig', 'summary_df', 'remaining_df']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]


def render_sidebar(authenticator):
    # User is authenticated - get info from session state
    name = st.session_state.get('name')
    username = st.session_state.get('username')
    # Display user info and logout button in sidebar
    with st.sidebar:
        st.write(f"👤 Welcome, **{name}**!")
        
        # Check if logout button was clicked
        # Store previous authentication status to detect logout
        prev_auth_status = st.session_state.get('prev_authentication_status', True)
        
        authenticator.logout(location='sidebar')
        
        # If authentication status changed from True to False/None, clear analysis results
        current_auth_status = st.session_state.get('authentication_status', None)
        if prev_auth_status == True and current_auth_status != True:
            clear_analysis_results()
        
        # Update previous authentication status
        st.session_state.prev_authentication_status = current_auth_status
        
        st.divider()
        st.caption(f"Logged in as: `{username}`")