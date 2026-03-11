import streamlit as st


def render_info_tab(tab):
    """
    Render the Info tab with app documentation and usage instructions.
    """
    with tab:
        st.header("ℹ️ About This App")
        
        st.divider()
        st.warning("""
        **⚠️ DISCLAIMER**
        
        This application is provided "as is" without warranty of any kind. By using this app, you acknowledge and agree that:
        
        - You are solely responsible for the security and confidentiality of your financial data
        - The app developer assumes no liability for any loss, damage, or unauthorized access to your financial information
        - You use this application at your own risk
        - It is your responsibility to follow best practices for data security, including deleting sensitive files after use
        - No guarantee is made regarding the accuracy of categorization or analysis results
        
        **Use this application responsibly and always maintain backups of your important financial records.**
        """)
        st.divider()


        # Overview section
        st.markdown("""
        ## 📊 Budget Analysis & Credit Card Categorization App
        
        This application helps you analyze and categorize your credit card and bank transactions 
        automatically. Upload your transaction data, define custom categories with keyword searches, 
        and get visual insights into your spending patterns.
        
        ---
        """)
        
        # How to Use section
        st.markdown("""
        ## 🚀 How to Use This App
        
        > 🎁 **New User?** This app comes with a [`sample_transactions.csv`](sample_transactions.csv:1) file and
        > [`default_config.json`](default_config.json:1) to help you get started! You can view the sample file
        > in the Data Import tab to see how the app works, or use your own transaction data right away.
        
        ### Step 1: Import Your Transaction Data
        
        Navigate to the **📁 Data Import** tab to get started:
        
        1. **Upload CSV Files**: Click the file uploader and select one or more CSV files containing 
           your transaction data (credit card statements, bank exports, etc.)
        
        2. **Map Columns**: For each uploaded file, specify which columns contain:
           - **Date**: Transaction date
           - **Amount**: Transaction amount (positive or negative)
           - **Description**: Transaction description/merchant name
        
        3. **Save Configuration**: Click "💾 Save Column Mappings" to store your settings
        
        > 💡 **Tip**: The app remembers your column mappings, so you only need to configure each 
        > file type once!
        
        ---
        
        ### Step 2: Configure Categories
        
        Go to the **📊 Main** tab to set up your spending categories:
        
        1. **Edit Configuration**: Use the JSON editor to define your categories and keywords
        
        2. **Category Structure**: Categories are defined as JSON objects with keywords:
           ```json
           {
               "Groceries": ["WHOLE FOODS", "TRADER JOE", "SAFEWAY"],
               "Dining": ["RESTAURANT", "CAFE", "STARBUCKS"]
           }
           ```
        
        3. **Keyword Matching**: The app searches transaction descriptions for your keywords 
           (case-insensitive, partial matches)
        
        4. **Save Changes**: Click the "Save" button in the editor or press Ctrl+S
        
        > 💡 **Tip**: Use the "Copy-Friendly List" view in the analysis results to easily find 
        > descriptions for uncategorized transactions!
        
        ---
        
        ### Step 3: Run Analysis
        
        Still in the **📊 Main** tab:
        
        1. **Click "▶️ Run Analysis"**: The app will process all your uploaded transactions
        
        2. **View Results**: You'll see:
           - **Interactive Sunburst Chart**: Visual breakdown of spending by category
           - **Expense Summary Table**: Detailed amounts for each category and subcategory
           - **Uncategorized Transactions**: List of transactions that didn't match any category
        
        3. **Export Results**: Choose from multiple export formats:
           - CSV for spreadsheet analysis
           - Excel for formatted reports
           - HTML for sharing or archiving
           - Full Report with charts and tables combined
        
        ---
        
        ### Step 4: Refine Categories
        
        Improve your categorization over time:
        
        1. **Review Uncategorized**: Check the "Uncategorized Transactions" section
        
        2. **Add Keywords**: Copy descriptions from uncategorized transactions and add them
           to your category configuration
        
        3. **Re-run Analysis**: Click "▶️ Run Analysis" again to see updated results
        
        4. **Iterate**: Repeat until you've categorized all important transactions
        
        ---
        
        ### Step 5: Save Your Reports and Data
        
        Preserve your analysis results for future reference:
        
        1. **Export Options**: In the **📊 Main** tab, scroll to the "Export Options" section after running analysis
        
        2. **Choose Your Format**:
           - **📥 Export to CSV**: Download a spreadsheet-compatible file for further analysis
           - **📥 Export to Excel**: Get a formatted Excel workbook with your expense summary
           - **📥 Export Chart as HTML**: Save the interactive sunburst visualization
           - **📄 Export Full Report**: Download a complete HTML report with charts and tables combined
        
        3. **Save Locally**: All exports are downloaded to your computer for safekeeping
        
        > 💡 **Tip**: The Full Report option creates a standalone HTML file that you can open in any
        > browser without needing this app!
        
        ---
        
        ### Step 6: Clean Up Your Financial Data
        
        Protect your privacy by removing transaction files after analysis:
        
        1. **Navigate to Data Import Tab**: Go to the **📁 Data Import** tab
        
        2. **Remove Individual Files**: Click the "🗑️ Remove File" button for each file you want to delete
           - OR -
        3. **Clear All at Once**: Click "🗑️ Clear All Uploads" to remove all transaction files
        
        4. **Your Categories Are Safe**: Your keyword configuration and category setup will be preserved
           in your account for future use
        
        5. **Re-upload When Needed**: You can upload new transaction files anytime and your saved
           column mappings will still be available
        
        > ⚠️ **Privacy Note**: While the risk is low and your data is stored securely in your personal
        > account directory, it's good practice to delete financial transaction files after you've
        > exported your reports. This minimizes any potential exposure of sensitive financial information.
        
        ---
        """)

        
        
        
        