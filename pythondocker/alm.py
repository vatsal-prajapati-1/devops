import streamlit as st
import pandas as pd
import csv
import os
import subprocess
import sys
import uuid
import datetime
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Configuration ---
CASES_FILE = 'cases.csv'
RUNS_FILE = 'runs.csv'
SUITES_FILE = 'suites.csv'
EXECUTIONS_FILE = 'executions.csv'
SMART_RUNS_FILE = 'smart_runs.csv'
MAX_OUTPUT_DISPLAY = 5000

# --- Page Configuration ---
st.set_page_config(
    page_title='Test Case Orchestrator',
    page_icon='🧪',
    layout='wide',
    initial_sidebar_state='collapsed'
)

# --- Enhanced CSS Styling ---
st.markdown("""
<style>
    /* Main app background */
    .stApp {
        background-color: #f5f7fa;
    }
    
    /* Headers and text */
    h1, h2, h3 {
        color: #2c3e50;
    }
    
    /* Status colors */
    .status-passed { 
        color: #27ae60; 
        font-weight: bold; 
        background-color: #d4edda;
        padding: 2px 8px;
        border-radius: 4px;
    }
    .status-failed { 
        color: #e74c3c; 
        font-weight: bold;
        background-color: #f8d7da;
        padding: 2px 8px;
        border-radius: 4px;
    }
    .status-running { 
        color: #3498db; 
        font-weight: bold;
        background-color: #d1ecf1;
        padding: 2px 8px;
        border-radius: 4px;
    }
    .status-untested { 
        color: #7f8c8d;
        background-color: #e2e3e5;
        padding: 2px 8px;
        border-radius: 4px;
    }
    
    /* Card styling */
    .suite-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 15px;
    }
    
    .test-case-card {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #3498db;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* Tags */
    .tag-badge {
        background-color: #3498db;
        color: white;
        padding: 4px 10px;
        border-radius: 15px;
        font-size: 0.85em;
        margin: 2px;
        display: inline-block;
    }
    
    .feature-tag {
        background-color: #27ae60;
        color: white;
        padding: 4px 10px;
        border-radius: 15px;
        font-size: 0.85em;
        margin: 2px;
        display: inline-block;
    }
    
    .case-tag {
        background-color: #f39c12;
        color: white;
        padding: 4px 10px;
        border-radius: 15px;
        font-size: 0.85em;
        margin: 2px;
        display: inline-block;
    }
    
    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
    }
    
    /* Metrics */
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Report */
    .report-section {
        background-color: white;
        padding: 25px;
        border-radius: 10px;
        margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Execution card */
    .execution-card {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        border: 1px solid #e0e0e0;
    }
    
    /* Info boxes */
    .info-box {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
        padding: 10px 15px;
        margin: 10px 0;
        border-radius: 4px;
    }
    
    /* Success box */
    .success-box {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 10px 15px;
        margin: 10px 0;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

# --- Helper Functions ---
def ensure_csv_files():
    """Ensure CSV files exist with proper headers"""
    files = [
        (CASES_FILE, ['id', 'name', 'suite_tag', 'feature_tag', 'case_tag']),
        (RUNS_FILE, ['case_id', 'execution_id', 'timestamp', 'status', 'output']),
        (SUITES_FILE, ['id', 'name', 'description', 'suite_tag', 'feature_tags', 'path', 'thread_count', 'created_at']),
        (EXECUTIONS_FILE, ['execution_id', 'suite_id', 'start_time', 'end_time', 'status', 'total_cases', 'passed', 'failed', 'skipped']),
        (SMART_RUNS_FILE, ['smart_run_id', 'execution_ids', 'start_time', 'end_time', 'initial_total', 'final_passed', 'final_failed', 'iterations'])
    ]
    
    for file, headers in files:
        if not os.path.exists(file):
            try:
                with open(file, 'w', newline='') as f:
                    csv.writer(f).writerow(headers)
            except IOError as e:
                st.error(f"Failed to create {file}: {str(e)}")
                st.stop()

def generate_execution_id():
    """Generate a unique execution ID"""
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    return f"EX-{timestamp}-{str(uuid.uuid4())[:8]}"

def generate_smart_run_id():
    """Generate a unique smart run ID"""
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    return f"SR-{timestamp}-{str(uuid.uuid4())[:8]}"

def load_cases():
    """Load test cases from CSV"""
    try:
        df = pd.read_csv(CASES_FILE, dtype=str).fillna('')
        # Handle legacy column names
        if 'scenario_tag' in df.columns:
            df = df.rename(columns={'scenario_tag': 'feature_tag'})
        return df
    except Exception as e:
        st.error(f"Error loading cases: {str(e)}")
        return pd.DataFrame(columns=['id', 'name', 'suite_tag', 'feature_tag', 'case_tag'])

def load_runs():
    """Load test runs from CSV"""
    try:
        df = pd.read_csv(RUNS_FILE, dtype=str).fillna('')
        return df
    except Exception as e:
        st.error(f"Error loading runs: {str(e)}")
        return pd.DataFrame(columns=['case_id', 'execution_id', 'timestamp', 'status', 'output'])

def load_suites():
    """Load test suites from CSV"""
    try:
        df = pd.read_csv(SUITES_FILE, dtype=str).fillna('')
        # Handle legacy column names
        if 'scenario_tags' in df.columns:
            df = df.rename(columns={'scenario_tags': 'feature_tags'})
        return df
    except Exception as e:
        return pd.DataFrame(columns=['id', 'name', 'description', 'suite_tag', 'feature_tags', 'path', 'thread_count', 'created_at'])

def load_executions():
    """Load execution history from CSV"""
    try:
        return pd.read_csv(EXECUTIONS_FILE, dtype=str).fillna('')
    except Exception as e:
        return pd.DataFrame(columns=['execution_id', 'suite_id', 'start_time', 'end_time', 'status', 'total_cases', 'passed', 'failed', 'skipped'])

def load_smart_runs():
    """Load smart run history from CSV"""
    try:
        return pd.read_csv(SMART_RUNS_FILE, dtype=str).fillna('')
    except Exception as e:
        return pd.DataFrame(columns=['smart_run_id', 'execution_ids', 'start_time', 'end_time', 'initial_total', 'final_passed', 'final_failed', 'iterations'])

def save_df(df, filename):
    """Generic save function for dataframes"""
    try:
        df.to_csv(filename, index=False)
        return True
    except Exception as e:
        st.error(f"Error saving {filename}: {str(e)}")
        return False

def get_all_suite_tags():
    """Get all unique suite tags from suites"""
    suites = load_suites()
    if not suites.empty:
        return sorted(suites['suite_tag'].unique().tolist())
    return []

def get_feature_tags_for_suite(suite_tag):
    """Get feature tags for a specific suite"""
    suites = load_suites()
    suite_data = suites[suites['suite_tag'] == suite_tag]
    if not suite_data.empty:
        feature_tags_str = suite_data.iloc[0]['feature_tags']
        if feature_tags_str:
            return sorted([tag.strip() for tag in feature_tags_str.split(',') if tag.strip()])
    return []

def get_suite_info(suite_tag):
    """Get complete suite information"""
    suites = load_suites()
    suite_data = suites[suites['suite_tag'] == suite_tag]
    if not suite_data.empty:
        return suite_data.iloc[0].to_dict()
    return None

def create_suite(name, description, suite_tag, feature_tags, path, thread_count=5):
    """Create a new test suite"""
    suite_id = str(uuid.uuid4())
    suites = load_suites()
    created_at = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
    
    # Check if suite tag already exists
    if suite_tag in suites['suite_tag'].values:
        return None, f"Suite tag '{suite_tag}' already exists"
    
    feature_tags_str = ','.join(feature_tags) if isinstance(feature_tags, list) else feature_tags
    
    new_suite = [suite_id, name, description, suite_tag, feature_tags_str, path, str(thread_count), created_at]
    suites.loc[len(suites)] = new_suite
    
    if save_df(suites, SUITES_FILE):
        return suite_id, None
    return None, "Failed to save suite"

def update_suite(suite_id, name, description, feature_tags, path, thread_count):
    """Update an existing test suite"""
    suites = load_suites()
    idx = suites[suites['id'] == suite_id].index
    
    if len(idx) > 0:
        feature_tags_str = ','.join(feature_tags) if isinstance(feature_tags, list) else feature_tags
        suites.loc[idx[0], 'name'] = name
        suites.loc[idx[0], 'description'] = description
        suites.loc[idx[0], 'feature_tags'] = feature_tags_str
        suites.loc[idx[0], 'path'] = path
        suites.loc[idx[0], 'thread_count'] = str(thread_count)
        return save_df(suites, SUITES_FILE)
    return False

def delete_suite(suite_id):
    """Delete a test suite and its test cases"""
    suites = load_suites()
    suite_tag = suites[suites['id'] == suite_id]['suite_tag'].values[0]
    
    # Delete suite
    suites = suites[suites['id'] != suite_id]
    if not save_df(suites, SUITES_FILE):
        return False
    
    # Delete associated test cases
    cases = load_cases()
    cases = cases[cases['suite_tag'] != suite_tag]
    save_df(cases, CASES_FILE)
    
    return True

def add_case(name, suite_tag, feature_tag, case_tag):
    """Add a new test case"""
    case_id = str(uuid.uuid4())
    cases = load_cases()
    
    new_case = [case_id, name.strip(), suite_tag, feature_tag, case_tag.strip()]
    cases.loc[len(cases)] = new_case
    
    if save_df(cases, CASES_FILE):
        return case_id
    return None

def update_case(case_id, name, suite_tag, feature_tag, case_tag):
    """Update an existing test case"""
    cases = load_cases()
    idx = cases[cases['id'] == case_id].index
    
    if len(idx) > 0:
        cases.loc[idx[0]] = [case_id, name.strip(), suite_tag, feature_tag, case_tag.strip()]
        return save_df(cases, CASES_FILE)
    return False

def delete_case(case_id):
    """Delete a test case"""
    cases = load_cases()
    cases = cases[cases['id'] != case_id]
    
    if not save_df(cases, CASES_FILE):
        return False
    
    # Delete associated runs
    runs = load_runs()
    runs = runs[runs['case_id'] != case_id]
    save_df(runs, RUNS_FILE)
    
    return True

def manual_pass_case(case_id, execution_id=''):
    """Manually mark a test case as passed"""
    return record_run(case_id, 'Passed (Manual)', 'Manually marked as passed', execution_id)

def record_run(case_id, status, output='', execution_id=''):
    """Record a test run result"""
    try:
        runs = load_runs()
        timestamp = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
        
        if len(output) > MAX_OUTPUT_DISPLAY:
            output = output[:MAX_OUTPUT_DISPLAY] + '\n... (output truncated)'
        
        runs.loc[len(runs)] = [case_id, execution_id, timestamp, status, output]
        runs.to_csv(RUNS_FILE, index=False)
        return True
    except Exception as e:
        st.error(f"Error recording run: {str(e)}")
        return False

def run_cucumber_tests(tags, path, execution_id='', threads=1):
    """Execute Cucumber tests with specified tags"""
    original_dir = os.getcwd()
    
    try:
        if path and os.path.exists(path):
            os.chdir(path)
        
        mvn_cmd = './mvnw' if os.path.exists('./mvnw') else 'mvn'
        cmd = [mvn_cmd, 'clean', 'test']
        
        if execution_id:
            cmd.append(f'-DexecutionID={execution_id}')
        
        if tags:
            cmd.append(f'-Dtags={tags}')
        
        if threads > 1:
            cmd.append(f'-Dthreads={threads}')
        
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if proc.returncode == 0:
            return 'Passed', proc.stdout
        return 'Failed', (proc.stdout or '') + '\n' + (proc.stderr or '')
        
    except subprocess.TimeoutExpired:
        return 'Failed', 'Test execution timed out after 10 minutes'
    except Exception as e:
        return 'Failed', f'Error running test: {str(e)}'
    finally:
        os.chdir(original_dir)

def run_by_tags(suite_tag='', feature_tag='', thread_count=1, execution_id=None):
    """Run tests filtered by tag hierarchy"""
    if not execution_id:
        execution_id = generate_execution_id()
    
    cases_df = load_cases()
    executions_df = load_executions()
    
    # Determine which tag to use for execution
    if feature_tag:
        execution_tag = feature_tag
        filtered_cases = cases_df[(cases_df['suite_tag'] == suite_tag) & 
                                 (cases_df['feature_tag'] == feature_tag)]
    else:
        execution_tag = suite_tag
        filtered_cases = cases_df[cases_df['suite_tag'] == suite_tag]
    
    if filtered_cases.empty:
        return execution_id, 0, 0, 0, []
    
    # Get suite info
    suite_info = get_suite_info(suite_tag)
    path = suite_info['path'] if suite_info else '.'
    
    # Record execution start
    start_time = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
    new_execution = [execution_id, '', start_time, '', 'Running', 
                    str(len(filtered_cases)), '0', '0', '0']
    executions_df.loc[len(executions_df)] = new_execution
    save_df(executions_df, EXECUTIONS_FILE)
    
    # Run tests
    status, output = run_cucumber_tests(execution_tag, path, execution_id, thread_count)
    
    # Analyze results
    results = {'Passed': 0, 'Failed': 0, 'Skipped': 0}
    failed_case_ids = []
    
    if status == 'Passed':
        results['Passed'] = len(filtered_cases)
        for _, case in filtered_cases.iterrows():
            record_run(case['id'], 'Passed', 'Test passed', execution_id)
    else:
        results['Failed'] = len(filtered_cases)
        for _, case in filtered_cases.iterrows():
            record_run(case['id'], 'Failed', output, execution_id)
            failed_case_ids.append(case['id'])
    
    # Update execution record
    end_time = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
    executions_df = load_executions()
    exec_idx = executions_df[executions_df['execution_id'] == execution_id].index[0]
    executions_df.loc[exec_idx, 'end_time'] = end_time
    executions_df.loc[exec_idx, 'status'] = 'Completed'
    executions_df.loc[exec_idx, 'passed'] = str(results['Passed'])
    executions_df.loc[exec_idx, 'failed'] = str(results['Failed'])
    executions_df.loc[exec_idx, 'skipped'] = str(results['Skipped'])
    save_df(executions_df, EXECUTIONS_FILE)
    
    return execution_id, results['Passed'], results['Failed'], results['Skipped'], failed_case_ids

def smart_run_suite(suite_tag, feature_tag='', thread_count=1, max_iterations=3):
    """Smart run that re-runs failed tests until stable"""
    smart_run_id = generate_smart_run_id()
    start_time = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
    
    execution_ids = []
    iteration = 0
    total_passed = 0
    failed_case_ids = []
    initial_total = 0
    
    progress_placeholder = st.empty()
    
    # First run
    iteration = 1
    with progress_placeholder.container():
        st.info(f"🔄 Iteration {iteration} of {max_iterations} - Running all tests...")
    
    exec_id, passed, failed, skipped, failed_ids = run_by_tags(
        suite_tag, feature_tag, thread_count
    )
    
    initial_total = passed + failed + skipped
    total_passed = passed
    failed_case_ids = failed_ids
    execution_ids.append(exec_id)
    
    # Re-run failed tests
    while iteration < max_iterations and failed_case_ids:
        iteration += 1
        with progress_placeholder.container():
            st.info(f"🔄 Iteration {iteration} of {max_iterations} - Re-running {len(failed_case_ids)} failed tests...")
        
        exec_id = generate_execution_id()
        cases_df = load_cases()
        
        new_failed_ids = []
        for case_id in failed_case_ids:
            case = cases_df[cases_df['id'] == case_id].iloc[0]
            
            # Run individual test using case tag
            suite_info = get_suite_info(case['suite_tag'])
            path = suite_info['path'] if suite_info else '.'
            
            status, output = run_cucumber_tests(case['case_tag'], path, exec_id, 1)
            record_run(case_id, status, output, exec_id)
            
            if status == 'Passed':
                total_passed += 1
            else:
                new_failed_ids.append(case_id)
        
        failed_case_ids = new_failed_ids
        execution_ids.append(exec_id)
    
    progress_placeholder.empty()
    
    # Save smart run record
    end_time = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
    smart_runs_df = load_smart_runs()
    
    new_smart_run = [
        smart_run_id,
        ','.join(execution_ids),
        start_time,
        end_time,
        str(initial_total),
        str(total_passed),
        str(len(failed_case_ids)),
        str(iteration)
    ]
    smart_runs_df.loc[len(smart_runs_df)] = new_smart_run
    save_df(smart_runs_df, SMART_RUNS_FILE)
    
    return smart_run_id, initial_total, total_passed, len(failed_case_ids), iteration

def generate_final_report(smart_run_id):
    """Generate final report for client"""
    smart_runs = load_smart_runs()
    smart_run = smart_runs[smart_runs['smart_run_id'] == smart_run_id].iloc[0]
    
    cases_df = load_cases()
    runs_df = load_runs()
    
    exec_ids = smart_run['execution_ids'].split(',')
    smart_run_runs = runs_df[runs_df['execution_id'].isin(exec_ids)]
    
    # Get final status for each case
    failed_details = []
    
    for case_id in cases_df['id']:
        case_runs = smart_run_runs[smart_run_runs['case_id'] == case_id].sort_values('timestamp')
        if not case_runs.empty:
            final_status = case_runs.iloc[-1]['status']
            
            if final_status.startswith('Failed'):
                case_info = cases_df[cases_df['id'] == case_id].iloc[0]
                suite_info = get_suite_info(case_info['suite_tag'])
                failed_details.append({
                    'Test Case': case_info['name'],
                    'Suite': case_info['suite_tag'],
                    'Feature': case_info['feature_tag'],
                    'Case Tag': case_info['case_tag'],
                    'Project Path': suite_info['path'] if suite_info else 'N/A'
                })
    
    report_data = {
        'smart_run_id': smart_run_id,
        'date': datetime.datetime.now().strftime('%Y-%m-%d'),
        'time': datetime.datetime.now().strftime('%H:%M:%S'),
        'total_cases': int(smart_run['initial_total']),
        'passed': int(smart_run['final_passed']),
        'failed': int(smart_run['final_failed']),
        'pass_rate': f"{(int(smart_run['final_passed']) / int(smart_run['initial_total']) * 100):.1f}%",
        'iterations': smart_run['iterations'],
        'duration': calculate_duration(smart_run['start_time'], smart_run['end_time']),
        'failed_details': failed_details
    }
    
    return report_data

def calculate_duration(start_time_str, end_time_str):
    """Calculate duration between two timestamps"""
    start = datetime.datetime.fromisoformat(start_time_str)
    end = datetime.datetime.fromisoformat(end_time_str)
    duration = end - start
    return str(duration).split('.')[0]  # Remove microseconds

def get_status_badge(status):
    """Get HTML formatted status badge"""
    if status.startswith('Passed'):
        return f'<span class="status-passed">✓ {status}</span>'
    elif status.startswith('Failed'):
        return f'<span class="status-failed">✗ {status}</span>'
    elif status == 'Running':
        return f'<span class="status-running">⟳ {status}</span>'
    else:
        return f'<span class="status-untested">○ {status}</span>'

# --- Initialize Data ---
ensure_csv_files()

# --- Main App ---
st.title('🧪 Test Case Orchestrator')
st.markdown('**Smart Cucumber Test Management & Execution Platform**')

# --- Load Data ---
cases_df = load_cases()
runs_df = load_runs()
suites_df = load_suites()
executions_df = load_executions()
smart_runs_df = load_smart_runs()

# Calculate latest status
if not runs_df.empty:
    latest = runs_df.sort_values('timestamp').drop_duplicates('case_id', keep='last')
    status_df = latest[['case_id','status']].rename(columns={'case_id':'id'})
    cases_df = cases_df.merge(status_df, on='id', how='left')
else:
    cases_df['status'] = 'Untested'

cases_df['status'] = cases_df['status'].fillna('Untested')

# --- Header Metrics ---
st.markdown("### 📊 Overall Statistics")
col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Total Tests", len(cases_df))
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    passed = len(cases_df[cases_df['status'].str.startswith('Passed', na=False)])
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Passed", passed)
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    failed = len(cases_df[cases_df['status'].str.startswith('Failed', na=False)])
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Failed", failed)
    st.markdown('</div>', unsafe_allow_html=True)

with col4:
    if len(cases_df) > 0:
        pass_rate = (passed/len(cases_df)*100)
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Pass Rate", f"{pass_rate:.1f}%")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Pass Rate", "0%")
        st.markdown('</div>', unsafe_allow_html=True)

with col5:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Test Suites", len(suites_df))
    st.markdown('</div>', unsafe_allow_html=True)

with col6:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Executions", len(executions_df))
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# --- Tabs ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    '🎯 Test Management', 
    '📋 Test Cases', 
    '🚀 Smart Execution', 
    '📊 Test Runs', 
    '📈 Reports', 
    '⚙️ Settings'
])

# Tab 1: Test Management
with tab1:
    st.markdown("### Test Suite & Case Management")
    
    # Action buttons with better styling
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🗂️ Create New Suite", type="primary", use_container_width=True):
            st.session_state['action'] = 'create_suite'
    with col2:
        if st.button("➕ Add Test Case", type="primary", use_container_width=True):
            st.session_state['action'] = 'add_case'
    with col3:
        if st.button("✏️ Edit Suite", use_container_width=True):
            st.session_state['action'] = 'edit_suite'
    
    action = st.session_state.get('action', 'view')
    st.markdown("---")
    
    if action == 'create_suite':
        st.markdown("### 🗂️ Create New Test Suite")
        
        # Initialize feature tags
        if 'temp_feature_tags' not in st.session_state:
            st.session_state['temp_feature_tags'] = []
        
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Suite Name*", placeholder="User Management Suite")
            suite_tag = st.text_input("Suite Tag*", placeholder="@user-mgmt")
            path = st.text_input("Execution Path*", placeholder="/home/project/test-automation", 
                               help="Directory where mvn command will be executed")
            description = st.text_area("Description", placeholder="Suite for testing user management features", height=100)
        
        with col2:
            thread_count = st.slider("Thread Count", min_value=1, max_value=10, value=5,
                                   help="Number of parallel threads for execution")
            
            st.markdown("#### Feature Tags Management")
            
            # Display current tags
            if st.session_state['temp_feature_tags']:
                st.markdown("**Current Feature Tags:**")
                cols = st.columns(4)
                for idx, tag in enumerate(st.session_state['temp_feature_tags']):
                    with cols[idx % 4]:
                        if st.button(f"❌ {tag}", key=f"remove_{idx}"):
                            st.session_state['temp_feature_tags'].remove(tag)
                            st.rerun()
            
            # Add new tag
            new_feature = st.text_input("Add Feature Tag", placeholder="@login", key="new_feature_input")
            if st.button("➕ Add Feature Tag", type="secondary"):
                if new_feature and new_feature not in st.session_state['temp_feature_tags']:
                    st.session_state['temp_feature_tags'].append(new_feature)
                    st.rerun()
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Create Suite", type="primary", use_container_width=True):
                if not all([name, suite_tag, path]) or not st.session_state['temp_feature_tags']:
                    st.error("⚠️ All fields are required and at least one feature tag must be added")
                elif not os.path.exists(path):
                    st.error(f"⚠️ Path '{path}' does not exist")
                else:
                    suite_id, error = create_suite(name, description, suite_tag, 
                                                 st.session_state['temp_feature_tags'], path, thread_count)
                    if suite_id:
                        st.success(f"✅ Suite '{name}' created successfully!")
                        st.session_state['temp_feature_tags'] = []
                        st.session_state['action'] = 'view'
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"⚠️ {error}")
        
        with col2:
            if st.button("Cancel", use_container_width=True):
                st.session_state['temp_feature_tags'] = []
                st.session_state['action'] = 'view'
                st.rerun()
    
    elif action == 'add_case':
        st.markdown("### ➕ Add New Test Case")
        
        # Check if suites exist
        if suites_df.empty:
            st.error("⚠️ No test suites available. Please create a suite first.")
            if st.button("Go to Create Suite"):
                st.session_state['action'] = 'create_suite'
                st.rerun()
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Test Case Name*", placeholder="Verify user login with valid credentials")
                
                # Suite tag dropdown
                suite_tags = get_all_suite_tags()
                suite_tag = st.selectbox("Select Suite*", [''] + suite_tags,
                                        help="Select the test suite")
            
            with col2:
                # Feature tag dropdown - properly load based on selected suite
                feature_tags = []
                if suite_tag:
                    feature_tags = get_feature_tags_for_suite(suite_tag)
                
                feature_tag = st.selectbox("Select Feature*", [''] + feature_tags if feature_tags else [''],
                                         help="Select the feature within the suite")
                
                case_tag = st.text_input("Test Case Tag*", placeholder="@tc_login_001",
                                       help="Unique tag for this test case")
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Add Test Case", type="primary", use_container_width=True):
                    if not all([name, suite_tag, feature_tag, case_tag]):
                        st.error("⚠️ All fields are required")
                    else:
                        case_id = add_case(name, suite_tag, feature_tag, case_tag)
                        if case_id:
                            st.success(f"✅ Test case '{name}' added successfully!")
                            st.balloons()
                            st.session_state['action'] = 'view'
                            st.rerun()
            
            with col2:
                if st.button("Cancel", use_container_width=True):
                    st.session_state['action'] = 'view'
                    st.rerun()
    
    elif action == 'edit_suite':
        st.markdown("### ✏️ Edit Test Suite")
        
        if suites_df.empty:
            st.info("No suites available to edit.")
        else:
            suite_names = ['Select a suite...'] + suites_df['name'].tolist()
            selected = st.selectbox("Select Suite to Edit", suite_names)
            
            if selected != 'Select a suite...':
                suite_data = suites_df[suites_df['name'] == selected].iloc[0]
                suite_id = suite_data['id']
                
                # Initialize tags
                existing_tags = [t.strip() for t in suite_data['feature_tags'].split(',') if t.strip()]
                if 'edit_feature_tags' not in st.session_state:
                    st.session_state['edit_feature_tags'] = existing_tags.copy()
                
                col1, col2 = st.columns(2)
                
                with col1:
                    name = st.text_input("Suite Name*", value=suite_data['name'])
                    st.text_input("Suite Tag", value=suite_data['suite_tag'], disabled=True)
                    path = st.text_input("Execution Path*", value=suite_data['path'])
                    description = st.text_area("Description", value=suite_data['description'], height=100)
                
                with col2:
                    thread_count = st.slider("Thread Count", min_value=1, max_value=10, 
                                           value=int(suite_data['thread_count']))
                    
                    st.markdown("#### Feature Tags Management")
                    
                    # Display tags with remove option
                    if st.session_state['edit_feature_tags']:
                        st.markdown("**Current Feature Tags:**")
                        cols = st.columns(4)
                        for idx, tag in enumerate(st.session_state['edit_feature_tags']):
                            with cols[idx % 4]:
                                if st.button(f"❌ {tag}", key=f"edit_remove_{idx}"):
                                    st.session_state['edit_feature_tags'].remove(tag)
                                    st.rerun()
                    
                    # Add new tag
                    new_tag = st.text_input("Add Feature Tag", key="edit_new_tag")
                    if st.button("➕ Add Feature Tag", type="secondary", key="add_edit_tag"):
                        if new_tag and new_tag not in st.session_state['edit_feature_tags']:
                            st.session_state['edit_feature_tags'].append(new_tag)
                            st.rerun()
                
                st.markdown("---")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("✅ Update Suite", type="primary", use_container_width=True):
                        if update_suite(suite_id, name, description, 
                                      st.session_state['edit_feature_tags'], path, thread_count):
                            st.success("✅ Suite updated successfully!")
                            del st.session_state['edit_feature_tags']
                            st.session_state['action'] = 'view'
                            st.rerun()
                
                with col2:
                    if st.button("🗑️ Delete Suite", type="secondary", use_container_width=True):
                        if st.checkbox("I understand this will delete all test cases in this suite"):
                            if delete_suite(suite_id):
                                st.success("✅ Suite deleted successfully!")
                                del st.session_state['edit_feature_tags']
                                st.session_state['action'] = 'view'
                                st.rerun()
                
                with col3:
                    if st.button("Cancel", use_container_width=True):
                        if 'edit_feature_tags' in st.session_state:
                            del st.session_state['edit_feature_tags']
                        st.session_state['action'] = 'view'
                        st.rerun()
    
    else:  # View mode
        # Display suites
        if not suites_df.empty:
            st.markdown("### 📂 Test Suites")
            
            for _, suite in suites_df.iterrows():
                st.markdown('<div class="suite-card">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([3, 3, 2])
                
                with col1:
                    st.markdown(f"### {suite['name']}")
                    st.markdown(f'<span class="tag-badge">{suite["suite_tag"]}</span>', unsafe_allow_html=True)
                    st.caption(f"📁 {suite['path']}")
                
                with col2:
                    feature_tags = [t.strip() for t in suite['feature_tags'].split(',') if t.strip()]
                    st.markdown("**Features:**")
                    tags_html = ' '.join([f'<span class="feature-tag">{tag}</span>' for tag in feature_tags])
                    st.markdown(tags_html, unsafe_allow_html=True)
                
                with col3:
                    test_count = len(cases_df[cases_df['suite_tag'] == suite['suite_tag']])
                    st.metric("Test Cases", test_count)
                    st.caption(f"Threads: {suite['thread_count']}")
                
                if suite['description']:
                    st.caption(suite['description'])
                
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No test suites created yet. Click 'Create New Suite' to get started.")

# Tab 2: Test Cases View
with tab2:
    st.markdown("### 📋 Test Cases Overview")
    
    if cases_df.empty:
        st.info("No test cases available. Add test cases from the Test Management tab.")
    else:
        # Filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            suite_filter = st.selectbox("Filter by Suite", ['All'] + get_all_suite_tags())
        
        with col2:
            feature_filter = st.selectbox("Filter by Feature", ['All'])
            if suite_filter != 'All':
                feature_tags = get_feature_tags_for_suite(suite_filter)
                feature_filter = st.selectbox("Filter by Feature", ['All'] + feature_tags, key="feature_filter_2")
        
        with col3:
            search_term = st.text_input("🔍 Search test cases", placeholder="Search by name or tag...")
        
        # Apply filters
        filtered_df = cases_df.copy()
        
        if suite_filter != 'All':
            filtered_df = filtered_df[filtered_df['suite_tag'] == suite_filter]
        
        if feature_filter != 'All':
            filtered_df = filtered_df[filtered_df['feature_tag'] == feature_filter]
        
        if search_term:
            filtered_df = filtered_df[
                filtered_df['name'].str.contains(search_term, case=False, na=False) |
                filtered_df['case_tag'].str.contains(search_term, case=False, na=False)
            ]
        
        st.markdown(f"**Showing {len(filtered_df)} test cases**")
        
        # Group by suite and feature
        for suite_tag in sorted(filtered_df['suite_tag'].unique()):
            suite_cases = filtered_df[filtered_df['suite_tag'] == suite_tag]
            
            with st.expander(f"📂 {suite_tag} ({len(suite_cases)} cases)", expanded=True):
                for feature_tag in sorted(suite_cases['feature_tag'].unique()):
                    feature_cases = suite_cases[suite_cases['feature_tag'] == feature_tag]
                    
                    st.markdown(f"#### {feature_tag}")
                    
                    for _, case in feature_cases.iterrows():
                        st.markdown('<div class="test-case-card">', unsafe_allow_html=True)
                        
                        col1, col2, col3, col4 = st.columns([4, 2, 2, 2])
                        
                        with col1:
                            st.markdown(f"**{case['name']}**")
                            st.markdown(f'<span class="case-tag">{case["case_tag"]}</span>', unsafe_allow_html=True)
                        
                        with col2:
                            st.markdown(get_status_badge(case['status']), unsafe_allow_html=True)
                        
                        with col3:
                            if st.button("✅ Pass", key=f"pass_{case['id']}"):
                                if manual_pass_case(case['id']):
                                    st.success("Marked as passed")
                                    st.rerun()
                        
                        with col4:
                            if st.button("✏️ Edit", key=f"edit_{case['id']}"):
                                st.session_state['edit_case_id'] = case['id']
                                st.rerun()
                        
                        st.markdown('</div>', unsafe_allow_html=True)
        
        # Edit case dialog
        if 'edit_case_id' in st.session_state:
            case_id = st.session_state['edit_case_id']
            case_data = cases_df[cases_df['id'] == case_id].iloc[0]
            
            st.markdown("---")
            st.markdown("### ✏️ Edit Test Case")
            
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Test Case Name", value=case_data['name'], key="edit_name")
                case_tag = st.text_input("Test Case Tag", value=case_data['case_tag'], key="edit_tag")
            
            with col2:
                st.text_input("Suite", value=case_data['suite_tag'], disabled=True)
                st.text_input("Feature", value=case_data['feature_tag'], disabled=True)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("💾 Save Changes", type="primary"):
                    if update_case(case_id, name, case_data['suite_tag'], 
                                 case_data['feature_tag'], case_tag):
                        st.success("✅ Updated successfully!")
                        del st.session_state['edit_case_id']
                        st.rerun()
            
            with col2:
                if st.button("🗑️ Delete", type="secondary"):
                    if delete_case(case_id):
                        st.success("✅ Deleted successfully!")
                        del st.session_state['edit_case_id']
                        st.rerun()
            
            with col3:
                if st.button("Cancel"):
                    del st.session_state['edit_case_id']
                    st.rerun()

# Tab 3: Smart Execution
with tab3:
    st.markdown("### 🚀 Smart Test Execution")
    st.markdown('<div class="info-box">Smart execution automatically re-runs failed tests to handle flaky tests and get accurate results</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        exec_type = st.radio("Execution Type", ["Run by Suite", "Run by Suite + Feature"], horizontal=True)
        
        # Suite selection
        suite_tags = get_all_suite_tags()
        if not suite_tags:
            st.error("⚠️ No test suites available. Create a suite first.")
        else:
            suite_tag = st.selectbox("Select Suite", suite_tags)
            
            feature_tag = ''
            if exec_type == "Run by Suite + Feature":
                feature_tags = get_feature_tags_for_suite(suite_tag)
                if feature_tags:
                    feature_tag = st.selectbox("Select Feature", feature_tags)
                else:
                    st.warning("No features available for this suite")
            
            # Execution settings
            col_a, col_b = st.columns(2)
            with col_a:
                thread_count = st.slider("Thread Count", 1, 10, 5,
                                       help="Number of parallel threads")
            with col_b:
                max_iterations = st.slider("Max Re-runs", 1, 5, 3,
                                         help="Maximum number of re-run attempts for failed tests")
            
            # Preview
            preview_cases = cases_df[cases_df['suite_tag'] == suite_tag]
            if feature_tag:
                preview_cases = preview_cases[preview_cases['feature_tag'] == feature_tag]
            
            st.markdown(f'<div class="info-box">📊 Will execute **{len(preview_cases)}** test cases</div>', 
                       unsafe_allow_html=True)
            
            # Execute button
            if st.button("🚀 Start Smart Execution", type="primary", use_container_width=True):
                with st.spinner("Executing tests with smart re-runs..."):
                    smart_run_id, total, passed, failed, iterations = smart_run_suite(
                        suite_tag, feature_tag, thread_count, max_iterations
                    )
                
                st.markdown('<div class="success-box">', unsafe_allow_html=True)
                st.success("✅ Smart execution completed!")
                st.markdown(f"**Results:** Total: {total} | Passed: {passed} | Failed: {failed}")
                st.markdown(f"**Pass Rate:** {(passed/total*100):.1f}% | Iterations: {iterations}")
                st.markdown('</div>', unsafe_allow_html=True)
                
                if failed == 0:
                    st.balloons()
    
    with col2:
        st.markdown("#### Recent Smart Runs")
        if not smart_runs_df.empty:
            for _, run in smart_runs_df.tail(5).iterrows():
                st.markdown('<div class="execution-card">', unsafe_allow_html=True)
                st.caption(f"**{run['smart_run_id'][:15]}...**")
                total = int(run['initial_total'])
                passed = int(run['final_passed'])
                st.progress(passed/total if total > 0 else 0)
                st.text(f"✅ {passed}/{total} ({(passed/total*100):.0f}%)")
                st.caption(run['start_time'][:16])
                st.markdown('</div>', unsafe_allow_html=True)

# Tab 4: Test Runs
with tab4:
    st.markdown("### 📊 Test Run History")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Date filter
        date_filter = st.date_input("Filter by Date", value=datetime.date.today())
    
    with col2:
        # Execution ID filter
        exec_ids = ['All'] + sorted(executions_df['execution_id'].unique().tolist(), reverse=True)
        exec_filter = st.selectbox("Filter by Execution ID", exec_ids)
    
    with col3:
        # Run type filter
        run_type = st.radio("Run Type", ["All", "Smart Runs", "Individual Runs"], horizontal=True)
    
    # Display executions
    if run_type in ["All", "Individual Runs"]:
        st.markdown("#### Execution History")
        
        filtered_execs = executions_df.copy()
        
        # Apply date filter
        filtered_execs['date'] = pd.to_datetime(filtered_execs['start_time']).dt.date
        filtered_execs = filtered_execs[filtered_execs['date'] == date_filter]
        
        # Apply execution ID filter
        if exec_filter != 'All':
            filtered_execs = filtered_execs[filtered_execs['execution_id'] == exec_filter]
        
        if not filtered_execs.empty:
            for _, exec in filtered_execs.sort_values('start_time', ascending=False).iterrows():
                st.markdown('<div class="execution-card">', unsafe_allow_html=True)
                
                col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 2])
                
                with col1:
                    st.markdown(f"**{exec['execution_id']}**")
                    st.caption(f"{exec['start_time']} - {exec['end_time']}")
                
                with col2:
                    st.metric("Total", exec['total_cases'])
                
                with col3:
                    st.metric("Passed", exec['passed'])
                
                with col4:
                    st.metric("Failed", exec['failed'])
                
                with col5:
                    if exec['total_cases'] and int(exec['total_cases']) > 0:
                        pass_rate = (int(exec['passed']) / int(exec['total_cases'])) * 100
                        st.metric("Pass Rate", f"{pass_rate:.1f}%")
                
                # Show test details
                if st.button("View Details", key=f"view_{exec['execution_id']}"):
                    exec_runs = runs_df[runs_df['execution_id'] == exec['execution_id']]
                    for _, run in exec_runs.iterrows():
                        case_info = cases_df[cases_df['id'] == run['case_id']].iloc[0]
                        st.text(f"• {case_info['name']} - {run['status']}")
                
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No executions found for the selected date")
    
    if run_type in ["All", "Smart Runs"]:
        st.markdown("#### Smart Run History")
        
        if not smart_runs_df.empty:
            for _, run in smart_runs_df.sort_values('start_time', ascending=False).iterrows():
                run_date = pd.to_datetime(run['start_time']).date()
                if run_date == date_filter:
                    st.markdown('<div class="execution-card">', unsafe_allow_html=True)
                    
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 2])
                    
                    with col1:
                        st.markdown(f"**{run['smart_run_id']}**")
                        st.caption(f"{run['start_time']} - {run['end_time']}")
                        st.caption(f"Iterations: {run['iterations']}")
                    
                    with col2:
                        st.metric("Initial", run['initial_total'])
                    
                    with col3:
                        st.metric("Final Passed", run['final_passed'])
                    
                    with col4:
                        total = int(run['initial_total'])
                        passed = int(run['final_passed'])
                        if total > 0:
                            st.metric("Final Pass Rate", f"{(passed/total*100):.1f}%")
                    
                    st.markdown('</div>', unsafe_allow_html=True)

# Tab 5: Reports
with tab5:
    st.markdown("### 📈 Test Reports")
    
    if smart_runs_df.empty:
        st.info("No smart runs available. Execute tests first to generate reports.")
    else:
        # Select smart run
        st.markdown("#### Generate Final Report")
        smart_run_ids = smart_runs_df.sort_values('start_time', ascending=False)['smart_run_id'].tolist()
        
        selected_run = st.selectbox("Select Smart Run", smart_run_ids,
                                  format_func=lambda x: f"{x} - {smart_runs_df[smart_runs_df['smart_run_id']==x].iloc[0]['start_time'][:16]}")
        
        if st.button("📄 Generate Final Report", type="primary"):
            report = generate_final_report(selected_run)
            
            # Display report
            st.markdown('<div class="report-section">', unsafe_allow_html=True)
            
            st.markdown("## Test Execution Report")
            st.markdown(f"**Report Date:** {report['date']} {report['time']}")
            st.markdown(f"**Smart Run ID:** {report['smart_run_id']}")
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Tests", report['total_cases'])
            with col2:
                st.metric("Passed", report['passed'])
            with col3:
                st.metric("Failed", report['failed'])
            with col4:
                st.metric("Pass Rate", report['pass_rate'])
            
            st.markdown(f"**Execution Duration:** {report['duration']}")
            st.markdown(f"**Total Iterations:** {report['iterations']}")
            
            # Failed tests details
            if report['failed_details']:
                st.markdown("### Failed Test Cases")
                failed_df = pd.DataFrame(report['failed_details'])
                st.dataframe(failed_df, use_container_width=True, hide_index=True)
            else:
                st.markdown('<div class="success-box">✅ All tests passed!</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Export report
            report_text = f"""TEST EXECUTION REPORT
================================
Report Date: {report['date']} {report['time']}
Smart Run ID: {report['smart_run_id']}

SUMMARY
-------
Total Tests: {report['total_cases']}
Passed: {report['passed']}
Failed: {report['failed']}
Pass Rate: {report['pass_rate']}

Execution Duration: {report['duration']}
Total Iterations: {report['iterations']}

"""
            if report['failed_details']:
                report_text += "FAILED TEST CASES\n-----------------\n"
                for detail in report['failed_details']:
                    report_text += f"- {detail['Test Case']}\n"
                    report_text += f"  Suite: {detail['Suite']}\n"
                    report_text += f"  Feature: {detail['Feature']}\n"
                    report_text += f"  Tag: {detail['Case Tag']}\n\n"
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "📥 Download Report (TXT)",
                    data=report_text,
                    file_name=f"test_report_{report['date']}_{selected_run[:10]}.txt",
                    mime="text/plain"
                )
            
            with col2:
                # CSV export
                if report['failed_details']:
                    csv_df = pd.DataFrame(report['failed_details'])
                    csv_data = csv_df.to_csv(index=False)
                    st.download_button(
                        "📥 Download Failed Tests (CSV)",
                        data=csv_data,
                        file_name=f"failed_tests_{report['date']}_{selected_run[:10]}.csv",
                        mime="text/csv"
                    )

# Tab 6: Settings
with tab6:
    st.markdown("### ⚙️ System Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Data Management")
        
        st.markdown("**Export Data**")
        if st.button("📥 Export All Test Cases"):
            csv_data = cases_df.to_csv(index=False)
            st.download_button(
                "Download",
                data=csv_data,
                file_name=f"test_cases_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        
        if st.button("📥 Export All Suites"):
            csv_data = suites_df.to_csv(index=False)
            st.download_button(
                "Download",
                data=csv_data,
                file_name=f"test_suites_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    with col2:
        st.markdown("#### Danger Zone")
        
        if st.button("🗑️ Clear All Execution History", type="secondary"):
            if st.checkbox("I understand this will delete all execution history"):
                for file in [RUNS_FILE, EXECUTIONS_FILE, SMART_RUNS_FILE]:
                    if os.path.exists(file):
                        os.remove(file)
                st.success("✅ Execution history cleared")
                st.rerun()

# Footer
st.markdown("---")
st.markdown(
    '<p style="text-align: center; color: #7f8c8d;">Test Case Orchestrator v6.0 | Smart Cucumber Test Management</p>',
    unsafe_allow_html=True
)