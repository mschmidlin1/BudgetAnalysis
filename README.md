# 💰 Budget Analysis App

A Streamlit-based web application for analyzing credit card transactions and visualizing spending patterns. This app helps you categorize expenses, create interactive visualizations, and gain insights into your spending habits.

## ✨ Features

### 🔐 User Authentication
- Secure login system with user registration
- Individual user configurations and data isolation
- Session-based authentication with cookies

### 📊 Transaction Analysis
- **Multi-file CSV Import**: Upload multiple transaction files from different credit cards or banks
- **Flexible Column Mapping**: Map your CSV columns (Date, Amount, Description) to standardized format
- **Smart Transaction Filtering**: Automatically filters out card payments to focus on actual expenses
- **Nested Category Support**: Create unlimited levels of expense categories and subcategories

### 📈 Visualizations
- **Interactive Sunburst Charts**: Drill down into spending categories with Plotly visualizations
- **Expense Summary Tables**: Clean, formatted tables showing spending by category
- **HTML Reports**: Export comprehensive reports with charts and tables

### ⚙️ Configuration Management
- **JSON-based Configuration**: Define spending categories using flexible JSON structure
- **Code Editor Integration**: Edit configurations directly in the app with syntax highlighting
- **Example Configurations**: Pre-built examples to get started quickly
- **Per-user Settings**: Each user maintains their own category configurations

## 🚀 Getting Started

- Python 3.9.11

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd BudgetAnalysis
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up authentication**
   
   Create a `credentials.yaml` file in the project root:
   ```yaml
   credentials:
     usernames:
       # Users will be added through the registration interface
   cookie:
     name: budget_analysis_cookie
     key: your_secret_key_here  # Change this to a random secret key
     expiry_days: 30
   ```

4. **Run the application**
   ```bash
   streamlit run main.py
   ```

5. **Access the app**
   
   Open your browser and navigate to `http://localhost:8501`

## 📖 Usage Guide

### 1. Registration & Login

- On first launch, create an account using the "Create New Account" expander
- Login with your credentials
- Each user gets isolated configuration and data storage

### 2. Import Transaction Data

Navigate to the **📁 Data Import** tab:

1. **Upload CSV Files**: Click "Browse files" and select one or more CSV files containing transaction data
2. **Map Columns**: For each file, select which columns contain:
   - Date information
   - Transaction amounts
   - Transaction descriptions
3. **Save Configuration**: Click "💾 Save Column Mappings" to persist your settings

### 3. Configure Categories

Navigate to the **📊 Main** tab:

1. **Edit Configuration**: Use the built-in code editor to define your spending categories
2. **Category Structure**: Create nested categories using JSON format

#### Example Configuration

```json
{
  "search_strings": [
    {
      "Transportation": [
        {
          "Gas": ["SUNOCO", "SHELL", "EXXON"]
        },
        {
          "Car Maintenance": [
            "GOODYEAR AUTO",
            "JIFFY LUBE"
          ]
        }
      ]
    },
    {
      "Shopping": [
        {
          "Groceries": ["WEGMANS", "COSTCO"]
        },
        {
          "General": ["TARGET", "WALMART"]
        }
      ]
    },
    "AMAZON",
    {
      "Utilities": [
        "WATER BOARD",
        "WASTE",
        "TELEPHONE"
      ]
    }
  ]
}
```

**Configuration Rules:**
- Use strings for simple search patterns (case-insensitive matching)
- Use dictionaries for nested categories
- Unlimited nesting levels supported
- Transactions matching multiple patterns are assigned to the first match

### 4. Analyze Spending

1. **Load Configuration**: Click "Load Configuration" to apply your category settings
2. **View Visualizations**: 
   - Interactive sunburst chart shows spending breakdown
   - Click segments to drill down into subcategories
   - Hover for detailed amounts and percentages
3. **Review Tables**: See spending totals by top-level category
4. **Export Reports**: Generate HTML reports with all visualizations

## 🏗️ Project Structure

```
BudgetAnalysis/
├── main.py                          # Main application entry point
├── analysis_utils.py                # Core analysis and visualization functions
├── config_tools.py                  # Configuration file management
├── configs.py                       # Configuration constants
├── data_import_tab.py              # Data import UI component
├── info_tab.py                     # Information tab UI
├── login.py                        # Authentication UI
├── main_tab.py                     # Main analysis tab UI
├── sidebar.py                      # Sidebar UI component
├── upload_tools.py                 # File upload utilities
├── user_tools.py                   # User management utilities
├── credentials.yaml                # Authentication credentials (create this)
├── default_config.json             # Default category configuration
├── example_nested_config.json      # Example nested configuration
├── sample_transactions.csv         # Sample data for testing
├── requirements.txt                # Python dependencies
├── notebooks/
│   └── analysis_development.ipynb  # Development notebook
└── README.md                       # This file
```

## 🔧 Key Functions

### Analysis Utilities ([`analysis_utils.py`](analysis_utils.py))

- **`split_dataframe_by_search()`**: Filter transactions by search string
- **`summarize_search_category()`**: Calculate spending for a category
- **`process_search_strings()`**: Process nested category configurations
- **`create_sunburst_chart()`**: Generate interactive Plotly sunburst charts
- **`create_expense_table()`**: Create formatted expense summary tables
- **`combine_transaction_files()`**: Merge multiple transaction files
- **`create_html_report()`**: Export comprehensive HTML reports

### Configuration Management

- **`load_config()`**: Load user's category configuration
- **`save_config()`**: Save category configuration to JSON
- **`load_upload_config()`**: Load file column mappings
- **`save_upload_config()`**: Save file column mappings

## 📊 Data Format

### Input CSV Requirements

Your transaction CSV files should contain at least three columns:
- **Date**: Transaction date (any common format)
- **Amount**: Transaction amount (negative for expenses or positive, app auto-detects)
- **Description**: Transaction description/merchant name

### Example CSV Format

```csv
Date,Amount,Description
2024-01-15,-45.67,WEGMANS GROCERY STORE
2024-01-16,-32.50,SHELL GAS STATION
2024-01-17,-125.00,AMAZON.COM
```

## 🎨 Customization

### Modifying Categories

Edit your configuration JSON to match your spending patterns:
- Add merchant names as they appear in your transaction descriptions
- Create category hierarchies that match your budgeting needs
- Use partial matches (e.g., "AMAZON" matches "AMAZON.COM", "AMAZON PRIME", etc.)

### Styling

The app uses Streamlit's theming system. Customize by creating a `.streamlit/config.toml` file:

```toml
[theme]
primaryColor = "#4CAF50"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

## 🔒 Security Notes

- Change the default secret key in `credentials.yaml`
- User data is stored in separate directories per user
- Passwords are hashed using bcrypt
- Session cookies expire after configured days

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## 📝 License

This project is open source and available under the MIT License.

## 🐛 Troubleshooting

### Common Issues

**Issue**: "Module not found" errors
- **Solution**: Ensure all dependencies are installed: `pip install -r requirements.txt`

**Issue**: Authentication not working
- **Solution**: Verify `credentials.yaml` exists and has correct format

**Issue**: Transactions not categorizing correctly
- **Solution**: Check that search strings match the actual merchant names in your CSV files (case-insensitive)

**Issue**: Charts not displaying
- **Solution**: Ensure you have saved column mappings and loaded configuration

## 📧 Support

For questions or issues, please open an issue on the GitHub repository.

---

**Built with**: Streamlit, Plotly, Pandas, and ❤️
