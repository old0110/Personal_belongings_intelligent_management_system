from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import requests 
from openai import OpenAI 
import pymysql

app = Flask(__name__)
os.environ['FLASK_ENV'] = 'development'  # 明确指定为开发环境
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': '替换为你自己的user',
    'password': '替换为你自己的password',
    'database': 'personal_item_sys',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db_connection():
    return pymysql.connect(**DB_CONFIG)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def login():
    if 'username' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

# 添加注册路由
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 检查用户名是否已存在
                check_sql = "SELECT * FROM users WHERE username = %s"
                cursor.execute(check_sql, (username,))
                existing_user = cursor.fetchone()
                if existing_user:
                    return '用户名已存在，请选择其他用户名。', 400
                # 插入新用户
                insert_sql = "INSERT INTO users (username, password) VALUES (%s, %s)"
                cursor.execute(insert_sql, (username, password))
                conn.commit()
            return redirect(url_for('login'))
        except pymysql.Error as e:
            print(f"注册用户时出错: {e}")
            conn.rollback()
            return '注册失败，请稍后重试。', 500
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def do_login():
    username = request.form.get('username')
    password = request.form.get('password')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM users WHERE username = %s AND password = %s"
            cursor.execute(sql, (username, password))
            user = cursor.fetchone()
        if user:
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return 'Invalid credentials', 401
    finally:
        conn.close()

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/index')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 获取用户 ID
            user_sql = "SELECT id FROM users WHERE username = %s"
            cursor.execute(user_sql, (username,))
            user = cursor.fetchone()
            user_id = user['id']
            # 获取用户物品
            items_sql = "SELECT * FROM items WHERE user_id = %s"
            cursor.execute(items_sql, (user_id,))
            items = cursor.fetchall()
        return render_template('index.html', items=items)
    finally:
        conn.close()

@app.route('/add_item', methods=['GET', 'POST'])
def add_item():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        description = request.form.get('description')
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filename)
            username = session['username']
            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    # 获取用户 ID
                    user_sql = "SELECT id FROM users WHERE username = %s"
                    cursor.execute(user_sql, (username,))
                    user = cursor.fetchone()
                    user_id = user['id']
                    # 添加物品
                    add_sql = "INSERT INTO items (description, image, user_id) VALUES (%s, %s, %s)"
                    cursor.execute(add_sql, (description, file.filename, user_id))
                    conn.commit()
                return redirect(url_for('index'))
            finally:
                conn.close()
    return render_template('add_item.html')

@app.route('/edit_item/<int:item_id>', methods=['POST'])
def edit_item(item_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    new_description = request.form.get('description')
    username = session['username']
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 获取用户 ID
            user_sql = "SELECT id FROM users WHERE username = %s"
            cursor.execute(user_sql, (username,))
            user = cursor.fetchone()
            user_id = user['id']
            # 检查新描述是否重复
            check_sql = "SELECT * FROM items WHERE id != %s AND description = %s AND user_id = %s"
            cursor.execute(check_sql, (item_id, new_description, user_id))
            duplicate_item = cursor.fetchone()
            if duplicate_item:
                return '物体描述重复，请重新输入。', 400
            # 更新物品描述
            update_sql = "UPDATE items SET description = %s WHERE id = %s AND user_id = %s"
            cursor.execute(update_sql, (new_description, item_id, user_id))
            conn.commit()
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/delete_item/<int:item_id>', methods=['GET'])
def delete_item(item_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 获取用户 ID
            user_sql = "SELECT id FROM users WHERE username = %s"
            cursor.execute(user_sql, (username,))
            user = cursor.fetchone()
            user_id = user['id']
            # 获取要删除物品的图片文件名
            get_image_sql = "SELECT image FROM items WHERE id = %s AND user_id = %s"
            cursor.execute(get_image_sql, (item_id, user_id))
            item = cursor.fetchone()
            if item and item['image']:
                image_filename = item['image']
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                # 删除图片文件
                if os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except Exception as e:
                        print(f"删除图片文件 {image_path} 失败: {e}")
            # 删除物品
            delete_sql = "DELETE FROM items WHERE id = %s AND user_id = %s"
            cursor.execute(delete_sql, (item_id, user_id))
            conn.commit()
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/ai_chat', methods=['GET', 'POST'])
def ai_chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 获取用户 ID
            user_sql = "SELECT id FROM users WHERE username = %s"
            cursor.execute(user_sql, (username,))
            user = cursor.fetchone()
            user_id = user['id']
            # 获取物品描述
            items_sql = "SELECT description FROM items WHERE user_id = %s"
            cursor.execute(items_sql, (user_id,))
            items = cursor.fetchall()
        item_descriptions = [item['description'] for item in items]
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
                import traceback
                print(traceback.format_exc())
                answer = f"请求出错: {str(e)}"
            return jsonify(answer=answer)
        return render_template('ai_chat.html', item_info=item_info)
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)
