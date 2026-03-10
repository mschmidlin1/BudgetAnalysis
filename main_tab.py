import streamlit as st
import json
from code_editor import code_editor
import pandas as pd
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

def render_main_tab(tab1):

# ============================================================================
# MAIN TAB
# ============================================================================
    with tab1:
        st.subheader("Configuration Editor ⚙️")
        st.write("Edit your transaction search categories and keywords")

        # Editor size settings
        EDITOR_SIZES = {
            "Large Editor": 40,
            "Small Editor": 15
        }

        # User control for editor size
        editor_size_choice = st.radio(
            "Editor Size:",
            options=list(EDITOR_SIZES.keys()),
            index=1,  # Default to first option: "Large Editor"
            horizontal=True,
            help="Choose the number of lines visible in the code editor"
        )

        editor_height = EDITOR_SIZES[editor_size_choice]

        # Load configuration as Python list
        search_strings = load_config()

        # Convert to JSON string for editing
        config_json = json.dumps(search_strings, indent=4)

        # Code editor configuration with syntax highlighting
        editor_buttons = [{
            "name": "Copy",
            "feather": "Copy",
            "hasText": True,
            "alwaysOn": True,
            "commands": ["copyAll"],
            "style": {"top": "0.46rem", "right": "0.4rem"}
        }, {
            "name": "Save",
            "feather": "Save",
            "hasText": True,
            "alwaysOn": True,
            "commands": ["submit"],
            "style": {"top": "0.46rem", "right": "5rem"}
        }]

        # JSON editor with syntax highlighting
        response_dict = code_editor(
            config_json,
            lang="json",
            height=editor_height,
            theme="default",
            shortcuts="vscode",
            focus=False,
            buttons=editor_buttons,
            allow_reset=True,
            key=f"config_editor_{st.session_state.config_key}",
            options={"wrap": True}
        )

        # Handle the code editor response
        # The 'text' field is only populated when a submit event occurs (Save button in editor)
        if response_dict and response_dict.get('type') == "submit" and response_dict.get('text'):
            try:
                # Parse JSON from the editor
                new_search_strings = json.loads(response_dict['text'])
                
                # Validate structure
                if not isinstance(new_search_strings, list):
                    st.error("❌ Configuration must be a JSON list")
                else:
                    # Validate each item
                    valid = True
                    for item in new_search_strings:
                        if not isinstance(item, (dict, str)):
                            st.error("❌ Each item must be either a dictionary (categorized) or string (uncategorized)")
                            valid = False
                            break
                        if isinstance(item, dict):
                            for key, value in item.items():
                                if not isinstance(value, list):
                                    st.error(f"❌ Category '{key}' must have a list of keywords")
                                    valid = False
                                    break
                    
                    if valid:
                        # All validation passed
                        if save_config(new_search_strings):
                            st.success("✅ Configuration saved successfully!")
                            st.session_state.config_key += 1  # Reset editor
                            st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"❌ Invalid JSON syntax: {str(e)}")
            except Exception as e:
                st.error(f"❌ Error saving configuration: {str(e)}")

        # Reset button
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔄 Reset to Saved"):
                st.session_state.config_key += 1  # Change key to force new widget
                st.rerun()

        # Preview section
        st.divider()

        # ============================================================================
        # PROCESSING AND VISUALIZATION SECTION
        # ============================================================================

        st.subheader("Transaction Analysis 📊")
        st.write("Process your transaction files and visualize spending patterns")

        # Load transaction sheets from upload config
        transaction_sheets = load_upload_config()

        # Initialize session state for results
        if 'analysis_results' not in st.session_state:
            st.session_state.analysis_results = None
        if 'fig' not in st.session_state:
            st.session_state.fig = None
        if 'summary_df' not in st.session_state:
            st.session_state.summary_df = None
        if 'remaining_df' not in st.session_state:
            st.session_state.remaining_df = None

        # Run Analysis Button
        if st.button("▶️ Run Analysis", type="primary", use_container_width=True):
            try:
                with st.spinner("Processing transactions..."):
                    # Load the current search strings from config
                    SEARCH_STRINGS = load_config()
                    
                    if not SEARCH_STRINGS:
                        st.warning("⚠️ No search strings configured. Please add categories in the Configuration Editor above.")
                    elif not transaction_sheets:
                        st.warning("⚠️ No transaction files uploaded. Please upload and configure files in the Data Import tab.")
                    else:
                        # Step 1: Combine transaction files from user's uploaded_files directory
                        df = combine_transaction_files(
                            transaction_sheets,
                            base_path=get_user_upload_dir(),
                            parse_dates=True,
                            sort_by_date=False
                        )
                        
                        # Step 2: Process search strings
                        summed_transactions, remaining_df = process_search_strings(df, SEARCH_STRINGS)
                        
                        # Step 3: Create visualizations
                        fig = create_sunburst_chart(summed_transactions)
                        
                        # Step 4: Create summary table
                        summary_df = create_expense_table(summed_transactions)
                        
                        # Store results in session state
                        st.session_state.analysis_results = summed_transactions
                        st.session_state.fig = fig
                        st.session_state.summary_df = summary_df
                        st.session_state.remaining_df = remaining_df
                        
                        st.success("✅ Analysis completed successfully!")
                        
            except FileNotFoundError as e:
                st.error(f"❌ File not found: {str(e)}")
                st.info("💡 Make sure the transaction files exist in the '2025Transactions' folder")
            except Exception as e:
                st.error(f"❌ Error during analysis: {str(e)}")
                st.exception(e)

        # Display results if available
        if st.session_state.fig is not None and st.session_state.summary_df is not None:
            st.divider()
            
            # Display the sunburst chart
            st.subheader("Expense Breakdown Visualization")
            st.plotly_chart(st.session_state.fig, use_container_width=True)
            
            st.divider()
            
            # Display the summary table
            st.subheader("Expense Summary Table")
            
            # Format the dataframe for display
            display_df = st.session_state.summary_df.copy()
            
            # Apply custom styling using pandas Styler
            def highlight_rows(row):
                """Apply styling to specific rows"""
                if row['Subcategory'] == 'TOTAL':
                    return ['background-color: #4A90E2; font-weight: bold; color: white'] * len(row)
                elif row['Category'] == 'GRAND TOTAL':
                    return ['background-color: #2E7D32; font-weight: bold; color: white; font-size: 16px'] * len(row)
                else:
                    return [''] * len(row)
            
            # Format the Amount column as currency
            display_df['Amount'] = display_df['Amount'].apply(
                lambda x: f'${x:,.2f}' if pd.notna(x) else ''
            )
            
            # Apply styling using pandas Styler
            styled_df = display_df.style.apply(highlight_rows, axis=1)
            
            # Display with styling
            st.dataframe(
                styled_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Category": st.column_config.TextColumn("Category", width="medium"),
                    "Subcategory": st.column_config.TextColumn("Subcategory", width="medium"),
                    "Amount": st.column_config.TextColumn("Amount", width="small")
                }
            )
            
            # Display uncategorized transactions
            st.divider()
            st.subheader("Uncategorized Transactions")
            st.write("These transactions were not matched by any search category and are included in 'No Category'")
            
            if st.session_state.remaining_df is not None and not st.session_state.remaining_df.empty:
                # Display count and total
                uncategorized_count = len(st.session_state.remaining_df)
                uncategorized_total = abs(st.session_state.remaining_df['Amount'].abs().sum())
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Number of Transactions", uncategorized_count)
                with col2:
                    st.metric("Total Amount", f"${uncategorized_total:,.2f}")
                
                # Add tabs for different views
                view_tab1, view_tab2 = st.tabs(["📊 Table View", "📋 Copy-Friendly List"])
                
                with view_tab1:
                    # Display the dataframe (text is selectable by default)
                    st.dataframe(
                        st.session_state.remaining_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Source": st.column_config.TextColumn("Source", width="medium"),
                            "Date": st.column_config.DateColumn("Date", width="small"),
                            "Amount": st.column_config.NumberColumn("Amount", format="$%.2f", width="small"),
                            "Description": st.column_config.TextColumn("Description", width="large")
                        }
                    )
                    st.caption("💡 Tip: Click and drag to select text in any cell, then copy with Ctrl+C (Cmd+C on Mac)")
                
                with view_tab2:
                    # Create a copy-friendly list of descriptions
                    st.write("**Unique Transaction Descriptions** (easy to copy for adding to search strings):")
                    
                    # Get unique descriptions sorted alphabetically
                    unique_descriptions = sorted(st.session_state.remaining_df['Description'].unique())
                    
                    # Display in a text area for easy copying
                    descriptions_text = "\n".join(unique_descriptions)
                    st.text_area(
                        "All Unique Descriptions",
                        value=descriptions_text,
                        height=300,
                        help="Select all (Ctrl+A) and copy (Ctrl+C) to easily add these to your search strings",
                        label_visibility="collapsed"
                    )
                    
                    # Also provide a downloadable list
                    st.download_button(
                        label="📥 Download Descriptions as Text File",
                        data=descriptions_text,
                        file_name="uncategorized_descriptions.txt",
                        mime="text/plain"
                    )
            else:
                st.info("✅ All transactions have been categorized!")
            
            # Export options
            st.divider()
            st.subheader("Export Options")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("📥 Export to CSV"):
                    csv = st.session_state.summary_df.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name="expense_summary.csv",
                        mime="text/csv"
                    )
            
            with col2:
                if st.button("📥 Export to Excel"):
                    # Create Excel file in memory
                    from io import BytesIO
                    buffer = BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        st.session_state.summary_df.to_excel(writer, index=False, sheet_name='Expense Summary')
                    
                    st.download_button(
                        label="Download Excel",
                        data=buffer.getvalue(),
                        file_name="expense_summary.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            
            with col3:
                if st.button("📥 Export Chart as HTML"):
                    html_str = st.session_state.fig.to_html()
                    st.download_button(
                        label="Download Chart HTML",
                        data=html_str,
                        file_name="expense_chart.html",
                        mime="text/html"
                    )
            
            with col4:
                if st.button("📄 Export Full Report"):
                    # Create combined HTML report
                    from io import BytesIO
                    import tempfile
                    import os
                    
                    # Create temporary file
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as tmp:
                        tmp_path = tmp.name
                    
                    try:
                        # Generate the report
                        create_html_report(
                            st.session_state.analysis_results,
                            st.session_state.fig,
                            tmp_path
                        )
                        
                        # Read the file content
                        with open(tmp_path, 'r', encoding='utf-8') as f:
                            html_content = f.read()
                        
                        # Provide download button
                        st.download_button(
                            label="Download Full Report",
                            data=html_content,
                            file_name="expense_report.html",
                            mime="text/html"
                        )
                    finally:
                        # Clean up temporary file
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)

