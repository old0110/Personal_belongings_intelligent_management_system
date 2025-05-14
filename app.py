from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import json
import requests 
from openai import OpenAI 



app = Flask(__name__)
os.environ['FLASK_ENV'] = 'development'  # 明确指定为开发环境
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# 模拟用户数据库
users = {'user': '123456'}
# 物品信息存储文件
ITEMS_FILE = 'items.json'

# 加载物品信息
def load_items():
    if os.path.exists(ITEMS_FILE):
        with open(ITEMS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# 保存物品信息
def save_items(items):
    with open(ITEMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=4)

# 初始化物品列表
items = load_items()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def login():
    if 'username' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    username = request.form.get('username')
    password = request.form.get('password')
    if username in users and users[username] == password:
        session['username'] = username
        return redirect(url_for('index'))
    else:
        return 'Invalid credentials', 401

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/index')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', items=items)

# @app.route('/add_item', methods=['GET', 'POST'])
# def add_item():
#     if 'username' not in session:
#         return redirect(url_for('login'))
#     if request.method == 'POST':
#         description = request.form.get('description')
#         file = request.files['file']
#         if file and allowed_file(file.filename):
#             filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
#             file.save(filename)
#             items.append({'description': description, 'image': file.filename})
#             save_items(items)  # 保存物品信息
#             return redirect(url_for('index'))
#     return render_template('add_item.html')

@app.route('/edit_item/<int:item_index>', methods=['POST'])
def edit_item(item_index):
    if 'username' not in session:
        return redirect(url_for('login'))
    new_description = request.form.get('description')
    # 检查新描述是否重复
    for index, item in enumerate(items):
        if index != item_index and item['description'] == new_description:
            return '物体描述重复，请重新输入。', 400
    # 更新物品描述
    if 0 <= item_index < len(items):
        items[item_index]['description'] = new_description
        save_items(items)
    return redirect(url_for('index'))

@app.route('/delete_item/<int:item_index>', methods=['GET'])
def delete_item(item_index):
    if 'username' not in session:
        return redirect(url_for('login'))
    if 0 <= item_index < len(items):
        del items[item_index]
        save_items(items)
    return redirect(url_for('index'))


@app.route('/add_item', methods=['GET', 'POST'])
def add_item():
    if 'username' not in session:
        return redirect(url_for('login'))
    error = None  # 初始化错误信息
    if request.method == 'POST':
        description = request.form.get('description')
        file = request.files['file']
        # 检查描述是否重复
        for item in items:
            if item['description'] == description:
                error = '物体描述重复，请重新输入。'
                break
        if not error and file and allowed_file(file.filename):
            filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filename)
            items.append({'description': description, 'image': file.filename})
            save_items(items)  # 保存物品信息
            return redirect(url_for('index'))
    return render_template('add_item.html', error=error)

# 新增 AI 对话路由
@app.route('/ai_chat', methods=['GET', 'POST'])
def ai_chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # 读取物品描述
    items = load_items()
    item_descriptions = [item['description'] for item in items if 'description' in item]
    item_info = "你管理的物品有：" + ", ".join(item_descriptions)

    if request.method == 'POST':
        question = request.form.get('question')
        try:
            # 替换为你的 DeepSeek API 密钥
            client = OpenAI(
                api_key="替换为你自己的key",
                base_url="https://api.deepseek.com"
            )
            response = client.chat.completions.create(
                # model="deepseek-chat",
                model="deepseek-reasoner",
                messages=[
                    {"role": "system", "content": f"你是一个物品管理助手，下面是用户管理的物品信息：{item_info}。请回答用户关于这些物品的问题。"},
                    {"role": "user", "content": question}
                ],
                stream=False
            )
            answer = response.choices[0].message.content
        except Exception as e:
        #     answer = f"请求出错: {str(e)}"
        # return render_template('ai_chat.html', question=question, answer=answer, item_info=item_info)
            import traceback
            print(traceback.format_exc())
            answer = f"请求出错: {str(e)}"
        return jsonify(answer=answer)
    return render_template('ai_chat.html', item_info=item_info)

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
