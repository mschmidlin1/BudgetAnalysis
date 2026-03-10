import streamlit as st
from user_tools import save_credentials, initialize_user_config, load_users_dataframe, dataframe_to_config


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
                    # Reload config from Google Sheets to get the updated user data
                    users_df = load_users_dataframe()
                    updated_config = dataframe_to_config(users_df)
                    
                    # Merge the new user data from authenticator into config
                    if username_of_registered_user in config['credentials']['usernames']:
                        updated_config['credentials']['usernames'][username_of_registered_user] = config['credentials']['usernames'][username_of_registered_user]
                    
                    # Save the updated credentials to Google Sheets
                    save_credentials(updated_config)
                    
                    # Initialize default configuration for the new user
                    initialize_user_config(username_of_registered_user)
                    st.success('User registered successfully! Please login above.')
                    st.info(f"Username: `{username_of_registered_user}`")
            except Exception as e:
                st.error(f"Registration error: {e}")
        
        st.stop()