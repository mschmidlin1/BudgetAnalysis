
import numpy as np
import pandas as pd
from typing import Tuple
import plotly.express as px
from IPython.display import display
from pathlib import Path



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
    and the remaining dataframe after processing.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        The dataframe containing transaction data
    search_strings : list
        List containing strings and/or dictionaries with category groups
        
    Returns:
    --------
    tuple
        A tuple containing:
        - dict: Nested dictionary with summed expenses for each search string/category
        - pandas.DataFrame: Remaining dataframe after all transactions have been processed
    """
    result = {}
    df_copy = df.copy()  # Create a copy to avoid modifying the original

    for item in search_strings:
        if isinstance(item, str):
            # Simple string case
            remaining_df, amount_spent = summarize_search_category(df_copy, item)
            result[item] = amount_spent
            df_copy = remaining_df  # Update df_copy to exclude already processed transactions
            
        elif isinstance(item, dict):
            # Dictionary case - category group with multiple search strings
            for category_name, search_list in item.items():
                category_dict = {}
                
                for search_string in search_list:
                    remaining_df, amount_spent = summarize_search_category(df_copy, search_string)
                    category_dict[search_string] = amount_spent
                    df_copy = remaining_df  # Update df_copy to exclude already processed transactions
                
                result[category_name] = category_dict
    other = df_copy["Amount"].abs().sum()
    result["No Category"] = other
    return result, df_copy


def create_sunburst_chart(expense_summary):
    """Create a sunburst chart from nested expense data."""
    # Flatten the nested dictionary for plotly
    data = []
    
    for key, value in expense_summary.items():
        if isinstance(value, dict):
            # Category group with subcategories
            category_total = sum(value.values())
            for subkey, subvalue in value.items():
                data.append({
                    'category': key,
                    'subcategory': subkey,
                    'amount': subvalue,
                    'labels': subkey,
                    'parents': key
                })
            # Add parent category
            data.append({
                'category': key,
                'subcategory': '',
                'amount': category_total,
                'labels': key,
                'parents': ''
            })
        else:
            # Simple category
            data.append({
                'category': key,
                'subcategory': '',
                'amount': value,
                'labels': key,
                'parents': ''
            })
    
    df_plot = pd.DataFrame(data)
    
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
    Convert nested expense dictionary to a formatted DataFrame.
    
    Parameters:
    -----------
    expense_summary : dict
        Nested dictionary from process_search_strings()
        
    Returns:
    --------
    pandas.DataFrame
        Formatted table with Category, Subcategory, and Amount columns
    """
    rows = []
    
    for key, value in expense_summary.items():
        if isinstance(value, dict):
            # Category group with subcategories
            category_total = sum(value.values())
            
            # Add subcategory rows
            for subkey, subvalue in value.items():
                rows.append({
                    'Category': key,
                    'Subcategory': subkey,
                    'Amount': subvalue
                })
            
            # Add category total row
            rows.append({
                'Category': key,
                'Subcategory': 'TOTAL',
                'Amount': category_total
            })
            
            # Add blank separator row
            rows.append({
                'Category': '',
                'Subcategory': '',
                'Amount': None
            })
        else:
            # Simple category (no subcategories)
            rows.append({
                'Category': key,
                'Subcategory': '—',
                'Amount': value
            })
    
    # Remove last blank row if it exists
    if rows and rows[-1]['Category'] == '':
        rows.pop()
    
    df = pd.DataFrame(rows)
    
    # Add grand total row
    grand_total = df[df['Subcategory'] != 'TOTAL']['Amount'].sum()
    df = pd.concat([
        df,
        pd.DataFrame([{
            'Category': 'GRAND TOTAL',
            'Subcategory': '',
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
                'font-weight: bold; background-color: #0977ed' if x['Subcategory'] == 'TOTAL' 
                else 'background-color: #f0f0f0' if x['Category'] == '' 
                else 'font-weight: bold; background-color: #034713; font-size: 12pt' if x['Category'] == 'GRAND TOTAL'
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
        print(f"✓ Exported to {csv_file}")
    
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
        print(f"✓ Exported to {excel_file}")
    
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
        print(f"✓ Exported to {html_file}")
    
    if 'markdown' in formats:
        md_file = f'{filename}.md'
        df_export.to_markdown(md_file, index=False)
        exported_files['markdown'] = md_file
        print(f"✓ Exported to {md_file}")
    
    return exported_files


def create_html_report(expense_summary, fig, filename='expense_report.html'):
    """
    Create a comprehensive HTML report with both the sunburst chart and expense table.
    
    Parameters:
    -----------
    expense_summary : dict
        Nested dictionary from process_search_strings()
    fig : plotly.graph_objects.Figure
        The sunburst chart figure
    filename : str
        Output filename (default: 'expense_report.html')
        
    Returns:
    --------
    str
        Path to the generated HTML file
    """
    df = create_expense_table(expense_summary)
    
    # Get the chart HTML (without the full HTML wrapper)
    chart_html = fig.to_html(include_plotlyjs='cdn', div_id='sunburst-chart')
    
    # Create styled table HTML
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
            'font-weight: bold; background-color: #4A90E2; color: white' if x['Subcategory'] == 'TOTAL'
            else 'background-color: #f9f9f9' if x['Category'] == ''
            else 'font-weight: bold; background-color: #2E7D32; color: white; font-size: 12pt' if x['Category'] == 'GRAND TOTAL'
            else ''
            for _ in x
        ], axis=1)\
        .set_table_styles([
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
        ])\
        .hide(axis='index')
    
    table_html = styled_table.to_html()
    
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
    
    <div class="footer">
        <p>Generated on {pd.Timestamp.now().strftime('%B %d, %Y at %I:%M %p')}</p>
        <p>Budget Analysis Tool</p>
    </div>
</body>
</html>"""
    
    # Write to file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✓ HTML report exported to {filename}")
    return filename


def combine_transaction_files(transaction_sheets, base_path="2025Transactions",
                              parse_dates=True, sort_by_date=False):
    """Enhanced version with date parsing and sorting options."""
    combined_data = []
    
    for filename, columns in transaction_sheets.items():
        file_path = Path(base_path) / filename
        df = pd.read_csv(file_path)
        
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
        result_df['Date'] = pd.to_datetime(result_df['Date'])
    
    # Optional: Sort by date
    if sort_by_date:
        result_df = result_df.sort_values('Date').reset_index(drop=True)
    
    return result_df