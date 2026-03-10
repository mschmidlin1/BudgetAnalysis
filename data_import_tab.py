import streamlit as st
import json
from code_editor import code_editor
import pandas as pd
from pathlib import Path
from user_tools import (
    save_credentials,
    get_username,
    get_user_upload_dir,
    get_user_config_file,
    get_user_upload_config_file
)

from upload_tools import (
    ensure_upload_dir,
    save_upload_config,
    save_uploaded_file,
    load_uploaded_files,
    delete_uploaded_file,
    clear_all_uploads
)

from config_tools import (
    load_config,
    load_upload_config,
    save_upload_config,
    save_config
)
from analysis_utils import (
    combine_transaction_files,
    split_dataframe_by_search,
    summarize_search_category,
    process_search_strings,
    create_sunburst_chart,
    create_expense_table,
    display_expense_table,
    export_expense_table,
    create_html_report)





def render_data_import_tab(tab2):
# ============================================================================
# DATA IMPORT TAB
# ============================================================================
    with tab2:
        st.header("Data Import")
        st.write("Upload CSV files and map columns for transaction analysis")
        
        # Load existing uploaded files and mappings from disk
        saved_files = load_uploaded_files()
        saved_mappings = load_upload_config()
        
        # Step 1: File uploader - allows multiple files
        uploaded_files = st.file_uploader(
            "Upload CSV files",
            type=['csv'],
            accept_multiple_files=True,
            help="Upload one or more CSV files containing transaction data",
            key="file_uploader"
        )
        
        # Process newly uploaded files and save them to disk
        if uploaded_files:
            for uploaded_file in uploaded_files:
                if uploaded_file.name not in saved_files:
                    # Save file to disk
                    save_uploaded_file(uploaded_file)
                    st.success(f"✅ Saved {uploaded_file.name}")
        
        # Reload the list of saved files
        saved_files = load_uploaded_files()
        
        # Display uploaded files section
        if saved_files:
            st.divider()
            st.subheader("📋 Uploaded Files")
            st.write("Review and configure your uploaded transaction files")
            
            # Temporary storage for column mappings during this session
            temp_mappings = {}
            
            # Display each saved file with remove button in collapsible sections
            for file_name in saved_files:
                # Create collapsible section for each file
                with st.expander(f"📄 {file_name}", expanded=False):
                    # Remove button at the top of the expander
                    if st.button("🗑️ Remove File", key=f"remove_{file_name}", use_container_width=True):
                        delete_uploaded_file(file_name)
                        # Remove from config
                        if file_name in saved_mappings:
                            del saved_mappings[file_name]
                            save_upload_config(saved_mappings)
                        st.rerun()
                    
                    # Load and display file preview
                    try:
                        file_path = Path(get_user_upload_dir()) / file_name
                        df = pd.read_csv(file_path)
                        
                        st.markdown("**File Preview**")
                        st.dataframe(df.head(), use_container_width=True)
                        
                        # Column mapping interface
                        st.markdown("**Column Mapping**")
                        col1, col2, col3 = st.columns(3)
                        
                        # Get saved mapping or use defaults
                        current_mapping = saved_mappings.get(file_name, [
                            df.columns[0] if len(df.columns) > 0 else None,
                            df.columns[1] if len(df.columns) > 1 else None,
                            df.columns[2] if len(df.columns) > 2 else None
                        ])
                        
                        with col1:
                            date_col = st.selectbox(
                                "Date Column",
                                options=df.columns.tolist(),
                                index=df.columns.tolist().index(current_mapping[0]) if current_mapping[0] in df.columns else 0,
                                key=f"date_{file_name}",
                                help="Select the column containing transaction dates"
                            )
                        
                        with col2:
                            amount_col = st.selectbox(
                                "Amount Column",
                                options=df.columns.tolist(),
                                index=df.columns.tolist().index(current_mapping[1]) if current_mapping[1] in df.columns else 0,
                                key=f"amount_{file_name}",
                                help="Select the column containing transaction amounts"
                            )
                        
                        with col3:
                            description_col = st.selectbox(
                                "Description Column",
                                options=df.columns.tolist(),
                                index=df.columns.tolist().index(current_mapping[2]) if current_mapping[2] in df.columns else 0,
                                key=f"description_{file_name}",
                                help="Select the column containing transaction descriptions"
                            )
                        
                        # Store temporary mapping
                        temp_mappings[file_name] = [date_col, amount_col, description_col]
                        
                        # Show preview of selected columns
                        st.markdown("**Preview of Selected Columns**")
                        preview_df = df[[date_col, amount_col, description_col]].head(5)
                        st.dataframe(preview_df, use_container_width=True)
                        
                    except Exception as e:
                        st.error(f"Error loading {file_name}: {str(e)}")
            
            # Save mappings button
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("💾 Save Column Mappings", type="primary", use_container_width=True):
                    # Save mappings to config file
                    save_upload_config(temp_mappings)
                    st.success("✅ Column mappings saved successfully!")
                    st.info(f"Configured {len(temp_mappings)} file(s) for analysis")
                    st.rerun()
            
            with col2:
                if st.button("🗑️ Clear All Uploads"):
                    clear_all_uploads()
                    st.success("✅ All uploads cleared")
                    st.rerun()
            
            # Display current saved configuration
            if saved_mappings:
                st.divider()
                st.subheader("Current Saved Configuration")
                st.write("The following files and column mappings are saved and will be used for analysis:")
                
                config_display = []
                for file_name, columns in saved_mappings.items():
                    config_display.append({
                        "File": file_name,
                        "Date Column": columns[0],
                        "Amount Column": columns[1],
                        "Description Column": columns[2]
                    })
                
                st.dataframe(pd.DataFrame(config_display), use_container_width=True, hide_index=True)
                
                # Show the Python dictionary format
                with st.expander("View as Python Dictionary"):
                    st.code(f"transaction_sheets = {{\n" +
                        "\n".join([f'    "{k}": {v},' for k, v in saved_mappings.items()]) +
                        "\n}", language="python")
        else:
            st.info("👆 Upload CSV files above to get started")
