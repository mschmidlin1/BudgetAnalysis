
import numpy as np
import pandas as pd
from typing import Tuple
import plotly.express as px
from IPython.display import display
from pathlib import Path
import io
from storage.storage_utils import read_bytes, get_path_for_upload
from storage.user_tools import get_username



def split_dataframe_by_search(df, column_name, search_string):
    """
    Splits a dataframe into two sections based on whether rows contain a search string.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        The input dataframe to split
    column_name : str
        The name of the column to search in
    search_string : str
        The string to search for in the specified column
    
    Returns:
    --------
    tuple of (pandas.DataFrame, pandas.DataFrame)
        First dataframe: rows containing the search string
        Second dataframe: rows NOT containing the search string
    
    Example:
    --------
    >>> df = pd.DataFrame({'name': ['Alice', 'Bob', 'Charlie'], 'age': [25, 30, 35]})
    >>> contains, not_contains = split_dataframe_by_search(df, 'name', 'li')
    >>> print(contains)  # Alice, Charlie
    >>> print(not_contains)  # Bob
    """
    # Convert column to string type to handle non-string values
    search_column = df[column_name].astype(str)
    
    # Create boolean mask for rows containing the search string (case-sensitive)
    mask = search_column.str.contains(search_string, case=False, na=False)
    
    # Split dataframe based on mask
    df_contains = df[mask].copy()
    df_not_contains = df[~mask].copy()
    
    return df_contains, df_not_contains


def filter_ignored_descriptions(df, ignore_strings):
    """
    Remove transactions whose Description contains any ignore substring.

    Matching is case-insensitive substring search, same as category keywords.
    Matching rows are excluded entirely from analysis totals.

    Parameters
    ----------
    df : pandas.DataFrame
        Transaction data with a Description column.
    ignore_strings : list
        Substrings to filter out. Empty or None leaves df unchanged.

    Returns
    -------
    tuple of (pandas.DataFrame, pandas.DataFrame)
        kept_df: rows that should proceed to categorization
        ignored_df: rows filtered out (empty if nothing matched)
    """
    if df is None or df.empty:
        empty = df.copy() if df is not None else pd.DataFrame()
        return empty, empty.copy()

    if not ignore_strings:
        return df.copy(), df.iloc[0:0].copy()

    cleaned = [
        s.strip() for s in ignore_strings
        if isinstance(s, str) and s.strip()
    ]
    if not cleaned:
        return df.copy(), df.iloc[0:0].copy()

    search_column = df["Description"].astype(str)
    mask = pd.Series(False, index=df.index)
    for ignore_string in cleaned:
        mask = mask | search_column.str.contains(
            ignore_string, case=False, na=False, regex=False
        )

    ignored_df = df[mask].copy()
    kept_df = df[~mask].copy()
    return kept_df.reset_index(drop=True), ignored_df.reset_index(drop=True)


def summarize_search_category(df: pd.DataFrame, search_string: str) -> Tuple[pd.DataFrame, float]:
    """
    Summarize transactions matching a search category and return filtered data with total amount.
    
    This function splits a DataFrame based on a search string in the Description column,
    calculates the total amount spent for matching transactions, and returns both the
    non-matching transactions and the calculated total.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame containing transaction data. Must include 'Description' and 
        'Amount' columns. Amount values should be negative for expenses.
    search_string : str
        The search term to filter transactions by in the 'Description' column.
        This is passed to split_dataframe_by_search() for pattern matching.
    
    Returns
    -------
    Tuple[pd.DataFrame, float]
        A tuple containing:
        - other_df (pd.DataFrame): DataFrame containing all rows that do NOT match 
          the search string in the Description column
        - amount_spent (float): Total amount spent for transactions matching the 
          search string. Multiplied by -1 to convert negative expense values to 
          positive amounts.
    
    Notes
    -----
    - The function assumes expense amounts are stored as negative values in the 
      'Amount' column, hence the multiplication by -1 to get positive spending amounts.
    - Depends on split_dataframe_by_search() function to perform the actual filtering.
    
    Examples
    --------
    >>> df = pd.DataFrame({
    ...     'Description': ['Grocery Store', 'Gas Station', 'Restaurant'],
    ...     'Amount': [-50.00, -30.00, -25.00]
    ... })
    >>> remaining_df, total = summarize_search_category(df, 'Grocery')
    >>> print(f"Amount spent: ${total:.2f}")
    Amount spent: $50.00
    >>> print(f"Remaining transactions: {len(remaining_df)}")
    Remaining transactions: 2
    """
    search_df, other_df = split_dataframe_by_search(df, "Description", search_string)
    amount_spent = search_df["Amount"].abs().sum()
    return other_df, amount_spent


def process_search_strings(df, search_strings):
    """
    Process a list of search strings and return a nested dictionary of summed expenses
    with unlimited nesting levels and the remaining dataframe after processing.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        The dataframe containing transaction data
    search_strings : list
        List containing strings and/or dictionaries with category groups.
        Supports unlimited nesting levels.
        
    Returns:
    --------
    tuple
        A tuple containing:
        - dict: Nested dictionary with summed expenses for each search string/category
        - pandas.DataFrame: Remaining dataframe after all transactions have been processed
    """
    
    def process_item(item, df_remaining):
        """
        Recursively process an item (string or dict) and return results.
        
        Parameters:
        -----------
        item : str or dict
            The item to process
        df_remaining : pandas.DataFrame
            The dataframe with remaining unprocessed transactions
            
        Returns:
        --------
        tuple
            - result: The processed value (float for string, dict for nested structure)
            - df_remaining: Updated dataframe with processed transactions removed
        """
        if isinstance(item, str):
            # Base case: simple string search
            df_remaining, amount_spent = summarize_search_category(df_remaining, item)
            return amount_spent, df_remaining
            
        elif isinstance(item, dict):
            # Recursive case: nested dictionary
            nested_result = {}
            
            for key, value in item.items():
                if isinstance(value, list):
                    # Process list of items (can be strings or dicts)
                    sub_dict = {}
                    for sub_item in value:
                        sub_result, df_remaining = process_item(sub_item, df_remaining)
                        
                        # Determine the key name for this sub_item
                        if isinstance(sub_item, str):
                            sub_key = sub_item
                        elif isinstance(sub_item, dict):
                            # For nested dicts, merge the result directly
                            # This prevents creating extra wrapper levels
                            if isinstance(sub_result, dict):
                                sub_dict.update(sub_result)
                                continue
                            else:
                                sub_key = list(sub_item.keys())[0]
                        
                        sub_dict[sub_key] = sub_result
                    
                    nested_result[key] = sub_dict
                else:
                    # Single item (string or dict)
                    sub_result, df_remaining = process_item(value, df_remaining)
                    nested_result[key] = sub_result
            
            return nested_result, df_remaining
    
    result = {}
    df_copy = df.copy()  # Create a copy to avoid modifying the original

    for item in search_strings:
        if isinstance(item, str):
            # Simple string case
            amount_spent, df_copy = process_item(item, df_copy)
            result[item] = amount_spent
            
        elif isinstance(item, dict):
            # Dictionary case - process recursively
            for category_name, search_list in item.items():
                if isinstance(search_list, list):
                    category_dict = {}
                    for search_item in search_list:
                        sub_result, df_copy = process_item(search_item, df_copy)
                        
                        # Determine the key name
                        if isinstance(search_item, str):
                            key_name = search_item
                        elif isinstance(search_item, dict):
                            # For nested dicts, merge the result directly
                            if isinstance(sub_result, dict):
                                category_dict.update(sub_result)
                                continue
                            else:
                                key_name = list(search_item.keys())[0]
                        
                        category_dict[key_name] = sub_result
                    
                    result[category_name] = category_dict
                else:
                    # Single item
                    sub_result, df_copy = process_item(search_list, df_copy)
                    result[category_name] = sub_result
    
    other = df_copy["Amount"].abs().sum()
    result["No Category"] = other
    return result, df_copy


def create_sunburst_chart(expense_summary):
    """
    Create a sunburst chart from nested expense data with unlimited nesting levels.
    
    Parameters:
    -----------
    expense_summary : dict
        Nested dictionary with unlimited levels of nesting
        
    Returns:
    --------
    plotly.graph_objects.Figure
        Sunburst chart figure
    """
    
    def flatten_nested_dict(data, parent='', result_list=None):
        """
        Recursively flatten a nested dictionary into a list of records for plotly sunburst.
        
        Parameters:
        -----------
        data : dict or float
            The data to flatten (can be nested dict or numeric value)
        parent : str
            The parent label for this level
        result_list : list
            Accumulator for results
            
        Returns:
        --------
        list
            List of dictionaries with 'labels', 'parents', and 'amount' keys
        """
        if result_list is None:
            result_list = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    # Nested dictionary - calculate total and recurse
                    total = calculate_total(value)
                    
                    # Add this node
                    result_list.append({
                        'labels': key,
                        'parents': parent,
                        'amount': total
                    })
                    
                    # Recurse into children
                    flatten_nested_dict(value, parent=key, result_list=result_list)
                else:
                    # Leaf node (numeric value)
                    result_list.append({
                        'labels': key,
                        'parents': parent,
                        'amount': value
                    })
        
        return result_list
    
    def calculate_total(data):
        """
        Recursively calculate the total of all numeric values in a nested dictionary.
        
        Parameters:
        -----------
        data : dict or float
            The data to sum
            
        Returns:
        --------
        float
            Total sum of all leaf values
        """
        if isinstance(data, (int, float)):
            return data
        elif isinstance(data, dict):
            return sum(calculate_total(v) for v in data.values())
        else:
            return 0
    
    # Flatten the nested dictionary
    data = flatten_nested_dict(expense_summary)
    
    # Create DataFrame for plotly
    df_plot = pd.DataFrame(data)
    
    # Create sunburst chart
    fig = px.sunburst(
        df_plot,
        names='labels',
        parents='parents',
        values='amount',
        title='Expense Breakdown by Category',
        color='amount',
        color_continuous_scale='RdYlGn_r',
        height=1000,
        width=1000
    )
    
    fig.update_traces(textinfo='label+percent parent')
    return fig


def create_expense_table(expense_summary):
    """
    Convert nested expense dictionary to a formatted DataFrame showing only top-level categories.
    
    Parameters:
    -----------
    expense_summary : dict
        Nested dictionary from process_search_strings() with unlimited nesting levels
        
    Returns:
    --------
    pandas.DataFrame
        Formatted table with Category and Amount columns (top-level only)
    """
    
    def calculate_total(data):
        """
        Recursively calculate the total of all numeric values in a nested dictionary.
        
        Parameters:
        -----------
        data : dict or float
            The data to sum
            
        Returns:
        --------
        float
            Total sum of all leaf values
        """
        if isinstance(data, dict):
            return sum(calculate_total(v) for v in data.values())
        else:
            # Handle numeric types including numpy types
            try:
                return float(data)
            except (TypeError, ValueError):
                return 0
    
    rows = []
    
    # Process only top-level categories
    for key, value in expense_summary.items():
        total = calculate_total(value)
        rows.append({
            'Category': key,
            'Amount': total
        })
    
    df = pd.DataFrame(rows)
    
    # Add grand total row
    grand_total = df['Amount'].sum()
    df = pd.concat([
        df,
        pd.DataFrame([{
            'Category': 'GRAND TOTAL',
            'Amount': grand_total
        }])
    ], ignore_index=True)
    
    return df


def display_expense_table(expense_summary, style=True):
    """
    Display the expense table with nice formatting in Jupyter notebook.
    
    Parameters:
    -----------
    expense_summary : dict
        Nested dictionary from process_search_strings()
    style : bool
        Whether to apply styling (default: True)
        
    Returns:
    --------
    pandas.DataFrame
        The formatted table
    """
    df = create_expense_table(expense_summary)
    
    if style:
        # Apply styling for better visualization
        styled_df = df.style\
            .format({'Amount': '${:,.2f}'}, na_rep='')\
            .set_properties(**{
                'text-align': 'left',
                'font-size': '11pt'
            })\
            .set_properties(subset=['Amount'], **{
                'text-align': 'right'
            })\
            .apply(lambda x: [
                'font-weight: bold; background-color: #034713; font-size: 12pt' if x.name in df.index and df.loc[x.name, 'Category'] == 'GRAND TOTAL'
                else ''
                for _ in x
            ], axis=1)\
            .hide(axis='index')
        
        display(styled_df)
    else:
        display(df)
    
    return df


def export_expense_table(expense_summary, filename='expense_summary', formats=['csv', 'excel', 'html']):
    """
    Export the expense table to various file formats.
    
    Parameters:
    -----------
    expense_summary : dict
        Nested dictionary from process_search_strings()
    filename : str
        Base filename without extension (default: 'expense_summary')
    formats : list
        List of formats to export: 'csv', 'excel', 'html', 'markdown' (default: ['csv', 'excel', 'html'])
        
    Returns:
    --------
    dict
        Dictionary with format names as keys and file paths as values
    """
    df = create_expense_table(expense_summary)
    exported_files = {}
    
    # Format the Amount column for display
    df_export = df.copy()
    df_export['Amount'] = df_export['Amount'].apply(
        lambda x: f'${x:,.2f}' if pd.notna(x) else ''
    )
    
    if 'csv' in formats:
        csv_file = f'{filename}.csv'
        df_export.to_csv(csv_file, index=False)
        exported_files['csv'] = csv_file
    
    if 'excel' in formats:
        excel_file = f'{filename}.xlsx'
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Expense Summary')
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Expense Summary']
            for idx, col in enumerate(df_export.columns):
                max_length = max(
                    df_export[col].astype(str).apply(len).max(),
                    len(col)
                ) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = max_length
        
        exported_files['excel'] = excel_file
    
    if 'html' in formats:
        html_file = f'{filename}.html'
        
        # Create styled HTML
        styled_html = df.style\
            .format({'Amount': '${:,.2f}'}, na_rep='')\
            .set_properties(**{
                'text-align': 'left',
                'font-size': '11pt',
                'border': '1px solid #ddd',
                'padding': '8px'
            })\
            .set_properties(subset=['Amount'], **{
                'text-align': 'right'
            })\
            .apply(lambda x: [
                'font-weight: bold; background-color: #e6f2ff' if x['Subcategory'] == 'TOTAL' 
                else 'background-color: #f9f9f9' if x['Category'] == '' 
                else 'font-weight: bold; background-color: #d4edda; font-size: 12pt' if x['Category'] == 'GRAND TOTAL'
                else ''
                for _ in x
            ], axis=1)\
            .set_table_styles([
                {'selector': 'th', 'props': [
                    ('background-color', '#4CAF50'),
                    ('color', 'white'),
                    ('font-weight', 'bold'),
                    ('text-align', 'left'),
                    ('padding', '10px')
                ]},
                {'selector': 'table', 'props': [
                    ('border-collapse', 'collapse'),
                    ('width', '100%'),
                    ('margin', '20px 0')
                ]}
            ])\
            .hide(axis='index')
        
        styled_html.to_html(html_file)
        exported_files['html'] = html_file
    
    if 'markdown' in formats:
        md_file = f'{filename}.md'
        df_export.to_markdown(md_file, index=False)
        exported_files['markdown'] = md_file
    
    return exported_files


def create_html_report(expense_summary, fig, filename='expense_report.html',
                       recurring_df=None):
    """
    Create a comprehensive HTML report with sunburst, expense table, and recurring payments.

    Parameters:
    -----------
    expense_summary : dict
        Nested dictionary from process_search_strings()
    fig : plotly.graph_objects.Figure
        The sunburst chart figure
    filename : str
        Output filename (default: 'expense_report.html')
    recurring_df : pandas.DataFrame, optional
        Recurring payments table from detect_recurring_payments()

    Returns:
    --------
    str
        Path to the generated HTML file
    """
    from analysis.recurring_payments import format_recurring_for_display

    df = create_expense_table(expense_summary)

    # Get the chart HTML (without the full HTML wrapper)
    chart_html = fig.to_html(include_plotlyjs='cdn', div_id='sunburst-chart')

    table_styles = [
        {'selector': 'th', 'props': [
            ('background-color', '#4CAF50'),
            ('color', 'white'),
            ('font-weight', 'bold'),
            ('text-align', 'left'),
            ('padding', '10px'),
            ('border', '1px solid #ddd')
        ]},
        {'selector': 'table', 'props': [
            ('border-collapse', 'collapse'),
            ('width', '100%'),
            ('margin', '20px auto'),
            ('box-shadow', '0 2px 4px rgba(0,0,0,0.1)')
        ]}
    ]

    # Create styled expense summary table HTML
    styled_table = df.style\
        .format({'Amount': '${:,.2f}'}, na_rep='')\
        .set_properties(**{
            'text-align': 'left',
            'font-size': '11pt',
            'border': '1px solid #ddd',
            'padding': '8px'
        })\
        .set_properties(subset=['Amount'], **{
            'text-align': 'right'
        })\
        .apply(lambda x: [
            'font-weight: bold; background-color: #2E7D32; color: white; font-size: 12pt' if x.name in df.index and df.loc[x.name, 'Category'] == 'GRAND TOTAL'
            else ''
            for _ in x
        ], axis=1)\
        .set_table_styles(table_styles)\
        .hide(axis='index')

    table_html = styled_table.to_html()

    # Recurring payments section
    if recurring_df is not None and not recurring_df.empty:
        recurring_display = format_recurring_for_display(recurring_df).copy()
        amount_col = 'Recurring Amount'
        if amount_col in recurring_display.columns:
            recurring_display[amount_col] = recurring_display[amount_col].apply(
                lambda x: f"${float(x):,.2f}" if pd.notna(x) and x != '' else ''
            )
        for date_col in ('Start Date', 'End Date'):
            if date_col in recurring_display.columns:
                recurring_display[date_col] = pd.to_datetime(
                    recurring_display[date_col], errors='coerce'
                ).dt.strftime('%Y-%m-%d')

        styled_recurring = recurring_display.style\
            .set_properties(**{
                'text-align': 'left',
                'font-size': '11pt',
                'border': '1px solid #ddd',
                'padding': '8px'
            })\
            .set_table_styles(table_styles)\
            .hide(axis='index')
        recurring_section_body = (
            f'<div class="table-container">{styled_recurring.to_html()}</div>'
        )
    else:
        recurring_section_body = (
            '<p style="color: #666;">No recurring payments detected.</p>'
        )

    # Create complete HTML document
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Expense Analysis Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            text-align: center;
            padding: 30px 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .header p {{
            margin: 10px 0 0 0;
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .section {{
            background: white;
            padding: 30px;
            margin-bottom: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
            margin-top: 0;
        }}
        .chart-container {{
            margin: 20px 0;
        }}
        .table-container {{
            overflow-x: auto;
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
        }}
        @media print {{
            body {{
                background-color: white;
            }}
            .section {{
                box-shadow: none;
                page-break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>💰 Expense Analysis Report</h1>
        <p>Interactive Budget Breakdown and Summary</p>
    </div>
    
    <div class="section">
        <h2>📊 Expense Breakdown Visualization</h2>
        <div class="chart-container">
            {chart_html}
        </div>
        <p style="color: #666; font-style: italic; text-align: center;">
            Click on segments to drill down into categories. Hover for detailed information.
        </p>
    </div>
    
    <div class="section">
        <h2>📋 Expense Summary Table</h2>
        <div class="table-container">
            {table_html}
        </div>
    </div>

    <div class="section">
        <h2>🔄 Recurring Payments</h2>
        {recurring_section_body}
    </div>
    
    <div class="footer">
        <p>Generated on {pd.Timestamp.now().strftime('%B %d, %Y at %I:%M %p')}</p>
        <p>Budget Analysis Tool</p>
    </div>
</body>
</html>"""

    # Write to file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return filename


def combine_transaction_files(transaction_sheets, base_path="2025Transactions",
                              parse_dates=True, sort_by_date=False):
    """Enhanced version with date parsing and sorting options.

    Note: files are loaded from filesystem storage under the user's uploads prefix.
    """
    combined_data = []

    for filename, columns in transaction_sheets.items():
        username = get_username()
        if not username:
            raise Exception("No username found in session")

        relative_key = get_path_for_upload(username, filename)
        csv_bytes = read_bytes(relative_key)

        if csv_bytes is None:
            raise FileNotFoundError(f"Could not load {filename} from storage")

        df = pd.read_csv(io.BytesIO(csv_bytes))

        date_col, amount_col, description_col = columns

        standardized_df = pd.DataFrame({
            'Source': filename,
            'Date': df[date_col],
            'Amount': df[amount_col],
            'Description': df[description_col]
        })
        # Count negative vs positive transactions
        negative_count = (standardized_df['Amount'] < 0).sum()
        positive_count = (standardized_df['Amount'] > 0).sum()

        # Filter out card payments (paying the card off)
        if negative_count > positive_count:
            # Charges are negative, keep negative values
            standardized_df = standardized_df[standardized_df['Amount'] < 0]
        else:
            # Charges are positive, keep positive values
            standardized_df = standardized_df[standardized_df['Amount'] > 0]
        standardized_df.reset_index(drop=True, inplace=True)
        combined_data.append(standardized_df)

    result_df = pd.concat(combined_data, ignore_index=True)

    # Optional: Parse dates
    if parse_dates:
        result_df['Date'] = pd.to_datetime(result_df['Date'], format='mixed')

    # Optional: Sort by date
    if sort_by_date:
        result_df = result_df.sort_values('Date').reset_index(drop=True)

    return result_df


def filter_transactions_by_date(
    df: pd.DataFrame,
    start_date=None,
    end_date=None,
) -> pd.DataFrame:
    """Filter a transaction DataFrame to an inclusive date range."""
    if df is None or df.empty or "Date" not in df.columns:
        return df

    filtered = df.copy()
    filtered["Date"] = pd.to_datetime(filtered["Date"], format="mixed")

    if start_date is not None:
        start = pd.Timestamp(start_date)
        filtered = filtered[filtered["Date"] >= start]
    if end_date is not None:
        end_exclusive = pd.Timestamp(end_date) + pd.Timedelta(days=1)
        filtered = filtered[filtered["Date"] < end_exclusive]

    return filtered.reset_index(drop=True)
