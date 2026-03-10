import streamlit as st
from user_tools import save_credentials, initialize_user_config


def render_login(config, authenticator):
    # Check authentication status from session state
    if st.session_state.get('authentication_status') == False:
        st.error('Username/password is incorrect')
        st.stop()
    elif st.session_state.get('authentication_status') == None:
        st.warning('Please enter your username and password')
        
        
        # Add registration option
        st.divider()
        with st.expander("🆕 Create New Account"):
            try:
                email_of_registered_user, username_of_registered_user, name_of_registered_user = authenticator.register_user(
                    location='main',
                    captcha=False
                )
                if email_of_registered_user:
                    # Save the updated credentials to file
                    save_credentials(config)
                    # Initialize default configuration for the new user
                    initialize_user_config(username_of_registered_user)
                    st.success('User registered successfully! Please login above.')
                    st.info(f"Username: `{username_of_registered_user}`")
            except Exception as e:
                st.error(f"Registration error: {e}")
        
        st.stop()