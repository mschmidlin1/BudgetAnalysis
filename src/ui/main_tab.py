import streamlit as st
import json
from code_editor import code_editor
import pandas as pd
from storage.user_tools import (
    save_credentials,
    get_username,
    get_user_upload_dir,
    get_user_config_file,
    get_user_upload_config_file
)

from storage.upload_tools import (
    ensure_upload_dir,
    save_upload_config,
    save_uploaded_file,
    load_uploaded_files,
    delete_uploaded_file,
    clear_all_uploads
)

from storage.config_tools import (
    load_config,
    load_upload_config,
    load_ignore_strings,
    save_upload_config,
    save_config,
    save_ignore_strings
)
from analysis.analysis_utils import (
    combine_transaction_files,
    split_dataframe_by_search,
    summarize_search_category,
    process_search_strings,
    filter_ignored_descriptions,
    create_sunburst_chart,
    create_expense_table,
    display_expense_table,
    export_expense_table,
    create_html_report,
)
from analysis.recurring_payments import (
    assign_transaction_categories,
    detect_recurring_payments,
    format_recurring_for_display,
)
from ui.category_editor import (
    ensure_category_draft,
    normalize_search_strings,
    refresh_category_draft_from_storage,
    render_category_editor,
    set_category_draft,
    validate_search_strings,
)


def _render_json_config_editor():
    """Render the JSON code editor for search_strings (shared draft)."""
    EDITOR_SIZES = {
        "Large Editor": 40,
        "Small Editor": 15,
    }

    editor_size_choice = st.radio(
        "Editor Size:",
        options=list(EDITOR_SIZES.keys()),
        index=1,
        horizontal=True,
        help="Choose the number of lines visible in the code editor",
        key="json_config_editor_size",
    )
    editor_height = EDITOR_SIZES[editor_size_choice]

    ensure_category_draft()
    config_json = json.dumps(st.session_state.category_draft, indent=4)

    editor_buttons = [{
        "name": "Copy",
        "feather": "Copy",
        "hasText": True,
        "alwaysOn": True,
        "commands": ["copyAll"],
        "style": {"top": "0.46rem", "right": "0.4rem"},
    }, {
        "name": "Save",
        "feather": "Save",
        "hasText": True,
        "alwaysOn": True,
        "commands": ["submit"],
        "style": {"top": "0.46rem", "right": "5rem"},
    }]

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
        options={"wrap": True},
    )

    # The 'text' field is only populated when a submit event occurs (Save button)
    if response_dict and response_dict.get("type") == "submit" and response_dict.get("text"):
        try:
            new_search_strings = json.loads(response_dict["text"])
            ok, msg = validate_search_strings(new_search_strings)
            if not ok:
                st.error(f"❌ {msg}")
            else:
                normalized = normalize_search_strings(new_search_strings)
                if save_config(normalized):
                    set_category_draft(normalized)
                    st.success("✅ Configuration saved successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to save configuration")
        except json.JSONDecodeError as e:
            st.error(f"❌ Invalid JSON syntax: {str(e)}")
        except Exception as e:
            st.error(f"❌ Error saving configuration: {str(e)}")

    col1, _col2 = st.columns([1, 3])
    with col1:
        if st.button("🔄 Reset to Saved", key="json_config_editor_reset"):
            refresh_category_draft_from_storage()
            st.rerun()


@st.fragment
def _render_ignore_list_editor():
    """Ignored-description editor; fragment-scoped for Add/Remove/Reset."""
    st.subheader("Ignored Description Strings")
    st.caption(
        "Transactions whose Description contains any of these substrings "
        "are excluded from analysis (case-insensitive). This list is separate "
        "from the category editors above."
    )

    if "ignore_draft" not in st.session_state:
        st.session_state.ignore_draft = load_ignore_strings()
    if "ignore_input_key" not in st.session_state:
        st.session_state.ignore_input_key = 0

    add_col1, add_col2 = st.columns([4, 1])
    with add_col1:
        new_ignore = st.text_input(
            "Add ignore string",
            value="",
            placeholder="e.g. PAYMENT THANK YOU",
            label_visibility="collapsed",
            key=f"ignore_string_input_{st.session_state.ignore_input_key}",
        )
    with add_col2:
        if st.button("Add", use_container_width=True, key="add_ignore_btn"):
            candidate = (new_ignore or "").strip()
            if not candidate:
                st.warning("Enter a non-empty string to ignore.")
            elif any(
                s.casefold() == candidate.casefold()
                for s in st.session_state.ignore_draft
            ):
                st.info("That string is already in the ignore list.")
            else:
                st.session_state.ignore_draft = (
                    list(st.session_state.ignore_draft) + [candidate]
                )
                # Remount the text input empty (can't mutate widget state after instantiate)
                st.session_state.ignore_input_key += 1
                st.rerun(scope="fragment")

    if st.session_state.ignore_draft:
        st.write("Current ignore list:")
        for idx, ignore_str in enumerate(st.session_state.ignore_draft):
            row_col1, row_col2 = st.columns([5, 1])
            with row_col1:
                st.text(ignore_str)
            with row_col2:
                if st.button(
                    "Remove",
                    key=f"remove_ignore_{idx}",
                    use_container_width=True,
                ):
                    draft = list(st.session_state.ignore_draft)
                    draft.pop(idx)
                    st.session_state.ignore_draft = draft
                    st.rerun(scope="fragment")
    else:
        st.info("No ignore strings yet. Add substrings to exclude from analysis.")

    save_col1, save_col2 = st.columns([1, 3])
    with save_col1:
        if st.button("💾 Save ignore list", use_container_width=True):
            if save_ignore_strings(st.session_state.ignore_draft):
                st.session_state.ignore_draft = load_ignore_strings()
                st.success("Ignore list saved.")
                st.rerun()
            else:
                st.error("Failed to save ignore list.")
    with save_col2:
        if st.button("🔄 Reset ignore list", use_container_width=True):
            st.session_state.ignore_draft = load_ignore_strings()
            st.rerun(scope="fragment")


@st.fragment
def _render_analysis_results():
    """Display analysis charts/tables/exports without rebuilding editors."""
    if st.session_state.fig is None or st.session_state.summary_df is None:
        return

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
        if row["Category"] == "GRAND TOTAL":
            return [
                "background-color: #2E7D32; font-weight: bold; color: white; font-size: 16px"
            ] * len(row)
        else:
            return [""] * len(row)

    # Format the Amount column as currency
    display_df["Amount"] = display_df["Amount"].apply(
        lambda x: f"${x:,.2f}" if pd.notna(x) else ""
    )

    # Apply styling using pandas Styler
    styled_df = display_df.style.apply(highlight_rows, axis=1)

    # Display with styling
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Category": st.column_config.TextColumn("Category", width="large"),
            "Amount": st.column_config.TextColumn("Amount", width="medium"),
        },
    )

    # Recurring payments report
    st.divider()
    st.subheader("Recurring Payments")
    st.write(
        "Automatically detected recurring charges based on description, "
        "amount, and payment cadence."
    )

    if (
        st.session_state.get("recurring_df") is not None
        and not st.session_state.recurring_df.empty
    ):
        recurring_display = format_recurring_for_display(
            st.session_state.recurring_df
        ).copy()
        recurring_display["Recurring Amount"] = recurring_display[
            "Recurring Amount"
        ].apply(lambda x: f"${float(x):,.2f}" if pd.notna(x) else "")

        st.dataframe(
            recurring_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Recurring Expense Name": st.column_config.TextColumn(
                    "Recurring Expense Name", width="large"
                ),
                "Recurring Amount": st.column_config.TextColumn(
                    "Recurring Amount", width="small"
                ),
                "Credit Card": st.column_config.TextColumn(
                    "Credit Card", width="medium"
                ),
                "Category": st.column_config.TextColumn(
                    "Category", width="medium"
                ),
                "Start Date": st.column_config.DateColumn(
                    "Start Date", width="small"
                ),
                "End Date": st.column_config.DateColumn(
                    "End Date", width="small"
                ),
                "Frequency": st.column_config.TextColumn(
                    "Frequency", width="small"
                ),
                "Active": st.column_config.TextColumn(
                    "Active", width="small"
                ),
            },
        )

        csv_bytes = format_recurring_for_display(
            st.session_state.recurring_df
        ).to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download Recurring Payments CSV",
            data=csv_bytes,
            file_name="recurring_payments.csv",
            mime="text/csv",
        )
    else:
        st.info("No recurring payments detected for this analysis run.")

    # Display ignored transactions (excluded from totals)
    st.divider()
    st.subheader("Ignored Transactions")
    st.write(
        "These transactions matched an ignore string and were excluded from "
        "the sunburst, summary table, and grand total."
    )

    if (
        st.session_state.ignored_df is not None
        and not st.session_state.ignored_df.empty
    ):
        ignored_count = len(st.session_state.ignored_df)
        ignored_total = abs(st.session_state.ignored_df["Amount"].abs().sum())

        ign_col1, ign_col2 = st.columns(2)
        with ign_col1:
            st.metric("Number of Transactions", ignored_count)
        with ign_col2:
            st.metric("Total Amount", f"${ignored_total:,.2f}")

        st.dataframe(
            st.session_state.ignored_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Source": st.column_config.TextColumn("Source", width="medium"),
                "Date": st.column_config.DateColumn("Date", width="small"),
                "Amount": st.column_config.NumberColumn(
                    "Amount", format="$%.2f", width="small"
                ),
                "Description": st.column_config.TextColumn(
                    "Description", width="large"
                ),
            },
        )
    else:
        st.info("No transactions were ignored for this analysis run.")

    # Display uncategorized transactions
    st.divider()
    st.subheader("Uncategorized Transactions")
    st.write(
        "These transactions were not matched by any search category and are "
        "included in 'No Category'"
    )

    if (
        st.session_state.remaining_df is not None
        and not st.session_state.remaining_df.empty
    ):
        # Display count and total
        uncategorized_count = len(st.session_state.remaining_df)
        uncategorized_total = abs(
            st.session_state.remaining_df["Amount"].abs().sum()
        )

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
                    "Source": st.column_config.TextColumn(
                        "Source", width="medium"
                    ),
                    "Date": st.column_config.DateColumn("Date", width="small"),
                    "Amount": st.column_config.NumberColumn(
                        "Amount", format="$%.2f", width="small"
                    ),
                    "Description": st.column_config.TextColumn(
                        "Description", width="large"
                    ),
                },
            )
            st.caption(
                "💡 Tip: Click and drag to select text in any cell, then copy "
                "with Ctrl+C (Cmd+C on Mac)"
            )

        with view_tab2:
            # Create a copy-friendly list of descriptions
            st.write(
                "**Unique Transaction Descriptions** "
                "(easy to copy for adding to search strings):"
            )

            # Get unique descriptions sorted alphabetically
            unique_descriptions = sorted(
                st.session_state.remaining_df["Description"].unique()
            )

            # Display in a text area for easy copying
            descriptions_text = "\n".join(unique_descriptions)
            st.text_area(
                "All Unique Descriptions",
                value=descriptions_text,
                height=300,
                help=(
                    "Select all (Ctrl+A) and copy (Ctrl+C) to easily add these "
                    "to your search strings"
                ),
                label_visibility="collapsed",
            )

            # Also provide a downloadable list
            st.download_button(
                label="📥 Download Descriptions as Text File",
                data=descriptions_text,
                file_name="uncategorized_descriptions.txt",
                mime="text/plain",
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
                mime="text/csv",
            )

    with col2:
        if st.button("📥 Export to Excel"):
            # Create Excel file in memory
            from io import BytesIO

            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                st.session_state.summary_df.to_excel(
                    writer, index=False, sheet_name="Expense Summary"
                )

            st.download_button(
                label="Download Excel",
                data=buffer.getvalue(),
                file_name="expense_summary.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    with col3:
        if st.button("📥 Export Chart as HTML"):
            html_str = st.session_state.fig.to_html()
            st.download_button(
                label="Download Chart HTML",
                data=html_str,
                file_name="expense_chart.html",
                mime="text/html",
            )

    with col4:
        if st.button("📄 Export Full Report"):
            # Create combined HTML report
            import tempfile
            import os

            # Create temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", delete=False, encoding="utf-8"
            ) as tmp:
                tmp_path = tmp.name

            try:
                # Generate the report
                create_html_report(
                    st.session_state.analysis_results,
                    st.session_state.fig,
                    tmp_path,
                    recurring_df=st.session_state.get("recurring_df"),
                )

                # Read the file content
                with open(tmp_path, "r", encoding="utf-8") as f:
                    html_content = f.read()

                # Provide download button
                st.download_button(
                    label="Download Full Report",
                    data=html_content,
                    file_name="expense_report.html",
                    mime="text/html",
                )
            finally:
                # Clean up temporary file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)


def render_main_tab(tab1):

# ============================================================================
# MAIN TAB
# ============================================================================
    with tab1:
        st.subheader("Configuration Editor ⚙️")
        st.write("Edit your transaction search categories and keywords")

        category_tab, json_tab = st.tabs(["Category Editor", "JSON Editor"])
        with category_tab:
            render_category_editor()
        with json_tab:
            st.caption(
                "Advanced: edit the raw category JSON. Same data as the Category Editor."
            )
            _render_json_config_editor()

        # ============================================================================
        # IGNORE STRINGS — separate section below category editor tabs
        # ============================================================================
        st.divider()
        _render_ignore_list_editor()

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
        if 'ignored_df' not in st.session_state:
            st.session_state.ignored_df = None
        if 'recurring_df' not in st.session_state:
            st.session_state.recurring_df = None

        # Run Analysis Button
        if st.button("▶️ Run Analysis", type="primary", use_container_width=True):
            try:
                with st.spinner("Processing transactions..."):
                    # Load the current search strings from config
                    SEARCH_STRINGS = load_config()
                    IGNORE_STRINGS = load_ignore_strings()
                    
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

                        # Step 2: Filter out ignored descriptions before categorization
                        df, ignored_df = filter_ignored_descriptions(df, IGNORE_STRINGS)
                        
                        # Step 3: Process search strings
                        summed_transactions, remaining_df = process_search_strings(df, SEARCH_STRINGS)
                        
                        # Step 4: Create visualizations
                        fig = create_sunburst_chart(summed_transactions)
                        
                        # Step 5: Create summary table
                        summary_df = create_expense_table(summed_transactions)

                        # Step 6: Detect recurring payments (with category labels)
                        categorized_df = assign_transaction_categories(
                            df, SEARCH_STRINGS
                        )
                        recurring_df = detect_recurring_payments(categorized_df)
                        
                        # Store results in session state
                        st.session_state.analysis_results = summed_transactions
                        st.session_state.fig = fig
                        st.session_state.summary_df = summary_df
                        st.session_state.remaining_df = remaining_df
                        st.session_state.ignored_df = ignored_df
                        st.session_state.recurring_df = recurring_df
                        
                        st.success("✅ Analysis completed successfully!")
                        
            except FileNotFoundError as e:
                st.error(f"❌ File not found: {str(e)}")
                st.info("💡 Make sure the transaction files exist in the '2025Transactions' folder")
            except Exception as e:
                st.error(f"❌ Error during analysis: {str(e)}")
                st.exception(e)

        _render_analysis_results()

