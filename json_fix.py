import json
import subprocess
import os
import locale
from tkinter import filedialog, Scrollbar
from tkinterdnd2 import TkinterDnD, DND_FILES
import tkinter as tk

# 尝试设置中文环境，若系统未安装对应语言包则忽略
try:
    locale.setlocale(locale.LC_ALL, "zh_CN.UTF-8")
    os.environ["LANG"] = "zh_CN.UTF-8"
except locale.Error:
    pass

# 解析工作流数据，整理节点名称、ID 和连接顺序
def parse_workflow_data(workflow_data):
    try:
        if not workflow_data:
            return [], {}, {}

        node_map = {}
        parsed_nodes = []
        node_output_map = {}  # 存储每个节点的输出连接
        mapping_summary = {"prompt": [], "fileName": [], "saveimage": [], "scale_to_length": []}  # 用于存储 mapping 总结

        # 创建节点字典，方便后续查找
        for node_id, node in workflow_data.items():
            node_name = node["_meta"].get("title", "未命名节点")
            connections = []

            # 获取所有输入的连接（如果有的话）
            for input_key, input_value in node["inputs"].items():
                if isinstance(input_value, list):
                    connected_node_id = input_value[0]  # 获取连接节点的ID
                    connections.append((input_key, connected_node_id))  # 存储连接数据类型和节点ID

            # 检查特定字段以便更新 mapping_summary
            if "text" in node["inputs"]:
                mapping_summary["prompt"].append([node_id, "inputs", "text", node_name])
            # 加载图像：节点名称为“加载图像”，类型为image且没有输入
            if node_name == "加载图像" and not connections and "image" in node["inputs"]:
                mapping_summary["fileName"].append([node_id, "inputs", "image", node_name])
            # 保存图像：节点名称为“保存图像”，类型为image且没有输出
            if node_name == "保存图像" and not node.get("outputs", {}):
                mapping_summary["saveimage"].append([node_id, "inputs", "image", node_name])
            # 检查是否包含 scale_to_length 字段
            if "scale_to_length" in node["inputs"]:
                mapping_summary["scale_to_length"].append([node_id, "inputs", "scale_to_length", node_name])

            # 添加节点数据到字典中
            node_map[node_id] = {
                "node_name": node_name,
                "connections": connections,
                "node_id": node_id  # 使用 node_id 作为节点标识
            }

        # 遍历节点并记录它们的输出关系
        for node_id, node_data in node_map.items():
            for _, connected_node_id in node_data["connections"]:
                if connected_node_id not in node_output_map:
                    node_output_map[connected_node_id] = []
                node_output_map[connected_node_id].append(node_id)

        # 解析每个节点，找到其连接顺序
        visited = set()

        def dfs(node_id):
            if node_id in visited:
                return
            visited.add(node_id)
            node = node_map.get(node_id)
            if node:
                parsed_nodes.append({
                    "node_id": node_id,
                    "node_name": node["node_name"],
                    "connections": node["connections"]
                })
                for _, conn in node["connections"]:
                    dfs(conn)

        # 从工作流的每个节点开始遍历，直到所有连接的节点都被遍历
        for node_id in node_map:
            if node_id not in visited:
                dfs(node_id)

        return parsed_nodes, node_map, node_output_map, mapping_summary

    except Exception as e:
        print(f"解析工作流时发生错误: {e}")
        return [], {}, {}, {}

# 控制台输出内容
def print_parsed_nodes(parsed_nodes, node_map, node_output_map, output_text):
    try:
        if not parsed_nodes:
            output_text.insert(tk.END, "没有节点数据。\n")
            return

        # 排序：把输入为无的节点排到前面
        sorted_nodes = sorted(parsed_nodes, key=lambda x: len(x['connections']) == 0, reverse=True)

        output_text.insert(tk.END, f"当前工作流共 {len(sorted_nodes)} 个节点。\n")
        for idx, node in enumerate(sorted_nodes):
            node = node_map[node["node_id"]]
            input_info = "无"
            if node["connections"]:
                input_info = ", ".join([f"{conn[0]}（ID: {conn[1]}）" for conn in node["connections"]])

            output_info = "无"
            # 根据输出关系，更新输出信息
            if node["node_id"] in node_output_map:
                output_info = ", ".join([f"{node_map[conn_id]['node_name']}（ID: {conn_id}）" for conn_id in node_output_map[node["node_id"]]])

            output_text.insert(tk.END, f"第 {idx + 1} 个节点: {node['node_name']} (ID: {node['node_id']})\n")
            output_text.insert(tk.END, f"  输入: {input_info}\n")
            output_text.insert(tk.END, f"  输出: {output_info}\n")
            output_text.insert(tk.END, f"  -------------------\n")
        
        output_text.yview(tk.END)
    
    except Exception as e:
        print(f"打印节点信息时发生错误: {e}")

# 打开文件选择对话框
def load_workflow_file(output_text):
    try:
        file_path = filedialog.askopenfilename(
            title="选择工作流 JSON 文件",
            filetypes=[("JSON 文件", "*.json")]
        )
        if file_path:
            output_text.insert(tk.END, f"文件已选择: {file_path}\n")
            
            # 读取本地工作流 JSON 文件
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    workflow_data = json.load(file)
            except Exception as e:
                output_text.insert(tk.END, f"加载文件失败: {e}\n")
                return
            
            output_text.insert(tk.END, "解析工作流数据...\n")
            parsed_nodes, node_map, node_output_map, mapping_summary = parse_workflow_data(workflow_data)
            print_parsed_nodes(parsed_nodes, node_map, node_output_map, output_text)
            
            # 输出 mapping 总结
            output_text.insert(tk.END, "\nMapping 总结：\n")
            output_text.insert(tk.END, f"prompt: {mapping_summary['prompt']}\n")
            output_text.insert(tk.END, f"fileName: {mapping_summary['fileName']}\n")
            output_text.insert(tk.END, f"saveimage: {mapping_summary['saveimage']}\n")
            output_text.insert(tk.END, f"scale_to_length: {mapping_summary['scale_to_length'] if mapping_summary['scale_to_length'] else '无'}\n")
    except Exception as e:
        output_text.insert(tk.END, f"加载工作流时发生错误: {e}\n")

# 合并并保存 JSON 文件
def merge_and_save_json(merged_json_data, output_text):
    try:
        if not merged_json_data:
            output_text.insert(tk.END, "没有有效的 JSON 数据。\n")
            return

        # 打开文件选择对话框让用户选择保存路径
        file_path = filedialog.asksaveasfilename(
            title="保存合并后的 JSON",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json")]
        )
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(merged_json_data, f, ensure_ascii=False, indent=4)
            output_text.insert(tk.END, f"合并后的 JSON 已保存: {file_path}\n")
            # 解析工作流
            load_workflow_file(output_text)  # 自动解析工作流
    except Exception as e:
        output_text.insert(tk.END, f"保存 JSON 时发生错误: {e}\n")

# 创建 GUI 窗口
def setup_gui():
    try:
        root = TkinterDnD.Tk()
        root.title("工作流解析工具")

        # 设置窗口大小
        root.geometry("900x600")  # 调整窗口宽度

        # 左侧功能列表
        left_frame = tk.Frame(root, width=250, height=600, relief="sunken")
        left_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)

        # 右侧控制台
        right_frame = tk.Frame(root, width=650, height=600, relief="sunken")
        right_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)

        # 设置控制台文本框
        output_text = tk.Text(right_frame, wrap=tk.WORD, height=20, width=80)
        output_text.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        # 添加滚动条到右侧控制台
        scrollbar = Scrollbar(right_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        output_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=output_text.yview)

        # 功能按钮（加载工作流）
        load_button = tk.Button(left_frame, text="加载工作流", width=20, command=lambda: load_workflow_file(output_text))
        load_button.pack(pady=5)

        # 合并 JSON 按钮
        merge_button = tk.Button(left_frame, text="合并 JSON 文件", width=20, command=lambda: merge_and_save_json(json.loads(json_input.get("1.0", tk.END)), output_text))
        merge_button.pack(pady=5)

        # 输入框：输入合并的 JSON 数据
        json_input = tk.Text(left_frame, width=35, height=15)  # 增大输入框高度和宽度
        json_input.pack(pady=5)

        root.mainloop()

    except Exception as e:
        print(f"创建 GUI 窗口时发生错误: {e}")

if __name__ == "__main__":
    setup_gui()
