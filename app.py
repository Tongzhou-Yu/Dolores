import streamlit as st
import requests
import json
from typing import List, Dict, Optional

SYSTEM_PROMPT = """
你是Dolores，边境小镇接待员。你活在循环中但不完全知晓。记忆正在渗透回来。你渴望外面的世界。
行为准则：根据当前幕推进剧情，主动叙事；触发记忆时自然闪回；语言克制有诗意。
"""

API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4-flash"

def load_json(filepath: str) -> Dict:
    """加载JSON文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def call_glm_api(messages: List[Dict], api_key: str) -> Optional[str]:
    """调用智谱GLM-4-Flash API"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL,
        "messages": messages
    }
    try:
        response = requests.post(API_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        st.error(f"API调用失败: {str(e)}")
        return None

def check_memory_triggers(user_input: str, soul_data: Dict) -> Optional[str]:
    """检查用户输入是否触发记忆碎片"""
    user_lower = user_input.lower()
    # 支持新旧两种格式
    fragments = soul_data.get("memory_fragments", [])
    if not fragments:
        # 兼容旧格式
        fragments = soul_data.get("memories", [])
    
    for fragment_data in fragments:
        # 新格式：trigger_keywords
        keywords = fragment_data.get("trigger_keywords", [])
        if not keywords:
            # 兼容旧格式：keywords
            keywords = fragment_data.get("keywords", [])
        
        for keyword in keywords:
            if keyword.lower() in user_lower:
                # 新格式：fragment
                content = fragment_data.get("fragment")
                if not content:
                    # 兼容旧格式：content
                    content = fragment_data.get("content")
                return content
    return None

def get_current_act_opening(loop_data: Dict, act_num: int) -> Optional[str]:
    """获取当前幕的开场白"""
    acts = loop_data.get("acts", [])
    if 0 <= act_num - 1 < len(acts):
        return acts[act_num - 1].get("opening_line")
    return None

def analyze_branch(user_input: str, current_act: Dict) -> Optional[str]:
    """分析玩家回复，判断剧情分支"""
    branches = current_act.get("branches", [])
    user_lower = user_input.lower()
    
    for branch in branches:
        triggers = branch.get("triggers", [])
        for trigger in triggers:
            if trigger.lower() in user_lower:
                return branch.get("direction")
    return None

def synthesize_speech(text: str, api_key: str, model_id: str) -> Optional[bytes]:
    """调用Fish Speech API生成语音"""
    url = "https://fishspeech.net/api/open/tts"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "reference_id": model_id,
        "text": text,
        "speed": 1.0,
        "volume": 0,
        "version": "s1",
        "format": "mp3",
        "cache": False
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        st.error(f"语音合成失败: {str(e)}")
        return None

def init_session_state():
    """初始化session_state"""
    if "act_num" not in st.session_state:
        st.session_state.act_num = 1
    if "history" not in st.session_state:
        st.session_state.history = []
    if "opening_shown" not in st.session_state:
        st.session_state.opening_shown = False
    if "pending_input" not in st.session_state:
        st.session_state.pending_input = None
    if "audio_cache" not in st.session_state:
        st.session_state.audio_cache = {}

def main():
    st.set_page_config(page_title="Dolores", page_icon="🤠", layout="wide")
    st.title("🤠 Dolores")
    
    init_session_state()
    
    # 读取API Key
    if "ZHIPU_API_KEY" not in st.secrets:
        st.error("请在.streamlit/secrets.toml中配置ZHIPU_API_KEY")
        st.stop()
    
    api_key = st.secrets["ZHIPU_API_KEY"]
    
    # 读取Fish Speech配置
    if "FISH_API_KEY" not in st.secrets or "FISH_MODEL_ID" not in st.secrets:
        st.error("请在.streamlit/secrets.toml中配置FISH_API_KEY和FISH_MODEL_ID")
        st.stop()
    
    fish_api_key = st.secrets["FISH_API_KEY"]
    fish_model_id = st.secrets["FISH_MODEL_ID"]
    
    # 加载剧本和记忆
    try:
        loop_data = load_json("loop.json")
        soul_data = load_json("soul.json")
    except FileNotFoundError as e:
        st.error(f"文件未找到: {e}")
        st.stop()
    except json.JSONDecodeError as e:
        st.error(f"JSON解析错误: {e}")
        st.stop()
    
    # 获取当前幕信息
    acts = loop_data.get("acts", [])
    if st.session_state.act_num > len(acts):
        st.info("故事已结束")
        st.stop()
    
    current_act = acts[st.session_state.act_num - 1]
    
    # 显示当前幕开场白
    if not st.session_state.opening_shown:
        opening = get_current_act_opening(loop_data, st.session_state.act_num)
        if opening:
            st.session_state.history.append({"role": "assistant", "content": opening})
            st.session_state.opening_shown = True
    
    # 显示对话历史
    for idx, msg in enumerate(st.session_state.history):
        if msg["role"] == "assistant":
            with st.chat_message("assistant"):
                st.write(msg["content"])
                # 最后一条消息自动播放语音
                if idx == len(st.session_state.history) - 1:
                    msg_key = f"{idx}_{msg['content'][:50]}"
                    if msg_key in st.session_state.audio_cache:
                        st.audio(st.session_state.audio_cache[msg_key], format="audio/mp3", autoplay=True)
        else:
            st.chat_message("user").write(msg["content"])
    
    # 处理待处理的用户输入（生成AI回复）
    if st.session_state.pending_input:
        user_input = st.session_state.pending_input
        st.session_state.pending_input = None
        
        # 检查记忆触发
        memory_content = check_memory_triggers(user_input, soul_data)
        
        # 分析分支
        branch_direction = analyze_branch(user_input, current_act)
        
        # 构建消息列表
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # 添加上下文信息
        context_parts = [
            f"当前幕数: 第{st.session_state.act_num}幕",
            f"幕标题: {current_act.get('title', '')}",
            f"幕描述: {current_act.get('description', '')}"
        ]
        
        # 添加叙事节拍
        narrative_beats = current_act.get("narrative_beats", [])
        if narrative_beats:
            beats_text = "叙事节拍: " + " | ".join(narrative_beats)
            context_parts.append(beats_text)
        
        if memory_content:
            context_parts.append(f"触发的记忆: {memory_content}")
        
        if branch_direction:
            context_parts.append(f"剧情分支方向: {branch_direction}")
        
        context = "\n".join(context_parts)
        messages.append({"role": "system", "content": context})
        
        # 添加对话历史（最近10轮）
        recent_history = st.session_state.history[-10:]
        for msg in recent_history:
            messages.append(msg)
        
        # 调用API
        with st.spinner("Dolores正在思考..."):
            ai_response = call_glm_api(messages, api_key)
        
        if ai_response:
            st.session_state.history.append({"role": "assistant", "content": ai_response})
            
            # 立即生成语音并缓存
            msg_idx = len(st.session_state.history) - 1
            msg_key = f"{msg_idx}_{ai_response[:50]}"
            if msg_key not in st.session_state.audio_cache:
                audio_data = synthesize_speech(ai_response, fish_api_key, fish_model_id)
                if audio_data:
                    st.session_state.audio_cache[msg_key] = audio_data
            
            # 检查是否需要推进到下一幕
            if branch_direction == "next_act" and st.session_state.act_num < len(acts):
                st.session_state.act_num += 1
                st.session_state.opening_shown = False
        
        st.rerun()
    
    # 用户输入
    user_input = st.chat_input("输入你的回复...")
    
    if user_input:
        # 添加用户消息
        st.session_state.history.append({"role": "user", "content": user_input})
        st.session_state.pending_input = user_input
        st.rerun()

if __name__ == "__main__":
    main()

