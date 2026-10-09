<template>
  <div class="page">
    <aside class="sider">
      <button class="new-btn" type="button" @click="newChat">＋ 新对话</button>
      <nav class="conv-list">
        <div
          v-for="c in conversations"
          :key="c.id"
          class="conv-item"
          :class="{ on: c.id === currentId }"
        >
          <button type="button" class="conv-title" @click="selectChat(c.id)">
            {{ c.title }}
          </button>
          <button
            type="button"
            class="conv-del"
            title="删除对话"
            @click.stop="deleteChat(c.id)"
          >
            ×
          </button>
        </div>
      </nav>
    </aside>

    <McLayout class="shell">
      <McHeader title="P3 · 合同问答助手" logoImg="https://matechat.gitcode.com/logo.svg">
        <template #operationArea>
          <span class="hint">流式吐字 · 思维链 · 多会话</span>
        </template>
      </McHeader>

      <McLayoutContent v-if="!current || current.messages.length === 0" class="welcome">
        <McIntroduction
          logoImg="https://matechat.gitcode.com/logo2x.svg"
          title="高代码实战"
          subTitle="一个会查条款、会算违约金、带出处的 Agent"
          :description="description"
        />
        <McPrompt :list="introPrompt" direction="vertical" @itemClick="onSubmit($event.label)" />
      </McLayoutContent>

      <McLayoutContent v-else class="messages" ref="msgBox">
        <template v-for="(msg, idx) in current.messages" :key="idx">
          <McBubble
            v-if="msg.from === 'user'"
            :content="msg.content"
            align="right"
            :avatarConfig="userAvatar"
          />
          <div v-else class="bot-turn">
            <details v-if="msg.thinking" class="think" :open="msg.thinkOpen">
              <summary>思维链</summary>
              <pre>{{ msg.thinking }}</pre>
            </details>
            <details v-if="msg.steps.length" class="tool-trace" :open="msg.stepsOpen">
              <summary>工具调用</summary>
              <div class="tool-body">
                <div v-for="(st, i) in msg.steps" :key="i" class="tool-step" :class="st.tool">
                  <span class="tool-badge">{{ toolLabel(st.tool) }}</span>
                  <span v-if="st.phase === 'call'" class="tool-text">调用中… {{ argsBrief(st.args) }}</span>
                  <span v-else class="tool-text">{{ st.text }}</span>
                </div>
              </div>
            </details>
            <McBubble
              :content="msg.content || (msg.loading ? '正在思考…' : '')"
              align="left"
              :loading="msg.loading && !msg.content && !msg.thinking"
              :avatarConfig="botAvatar"
            />
          </div>
        </template>
      </McLayoutContent>

      <McLayoutSender>
        <McInput
          :value="inputValue"
          :maxLength="2000"
          :loading="sending"
          placeholder="输入问题后发送按钮才会亮起"
          @change="(e: string) => (inputValue = e)"
          @submit="onSubmit"
          @cancel="onCancel"
        />
      </McLayoutSender>
    </McLayout>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { consumeSSE } from "./useSSE";

type ToolStep = {
  tool: string;
  phase: "call" | "result";
  args?: Record<string, unknown>;
  text?: string;
};

type ChatMsg = {
  from: "user" | "model";
  content: string;
  thinking: string;
  loading?: boolean;
  steps: ToolStep[];
  thinkOpen?: boolean;
  stepsOpen?: boolean;
};

type Conversation = {
  id: string;
  title: string;
  messages: ChatMsg[];
};

const description = [
  "问一句，Agent 自己决定：先查知识库，还是先算数。",
  "左侧可开多个对话；同一对话里会记住上下文。",
  "思维链和工具调用会在答案上方流式出现。",
];

const introPrompt = [
  { value: "q1", label: "这份合同的付款期限是多久？", iconConfig: { name: "icon-info-o", color: "#5e7ce0" } },
  { value: "q2", label: "如果 11 月 20 日才付款，逾期几天、违约金多少？", iconConfig: { name: "icon-star", color: "#f5c10d" } },
  { value: "q3", label: "含税总价是多少？", iconConfig: { name: "icon-like", color: "#3ac295" } },
];

const userAvatar = { imgSrc: "https://matechat.gitcode.com/png/demo/userAvatar.svg" };
const botAvatar = { imgSrc: "https://matechat.gitcode.com/logo.svg" };

const inputValue = ref("");
const sending = ref(false);
const msgBox = ref<{ $el?: HTMLElement } | null>(null);
let abortCtl: AbortController | null = null;

function nid(): string {
  return crypto.randomUUID();
}

const conversations = ref<Conversation[]>([{ id: nid(), title: "新对话", messages: [] }]);
const currentId = ref(conversations.value[0].id);
const current = computed(() => conversations.value.find((c) => c.id === currentId.value) ?? conversations.value[0]);

function newChat() {
  if (sending.value) return;
  const c: Conversation = { id: nid(), title: "新对话", messages: [] };
  conversations.value.unshift(c);
  currentId.value = c.id;
}

function selectChat(id: string) {
  if (sending.value) return;
  currentId.value = id;
}

function deleteChat(id: string) {
  if (sending.value) return;
  const idx = conversations.value.findIndex((c) => c.id === id);
  if (idx === -1) return;
  conversations.value.splice(idx, 1);
  if (currentId.value === id) {
    currentId.value = conversations.value[0]?.id ?? "";
    if (!currentId.value) {
      const c: Conversation = { id: nid(), title: "新对话", messages: [] };
      conversations.value.push(c);
      currentId.value = c.id;
    }
  }
}

function toolLabel(tool: string): string {
  if (tool === "search_contract") return "🔎 知识库检索";
  if (tool === "calc_penalty") return "🧮 违约金计算";
  return "⚙️ " + tool;
}

function argsBrief(args?: Record<string, unknown>): string {
  if (!args) return "";
  if (typeof args.question === "string") return `「${args.question}」`;
  return Object.values(args).slice(0, 3).join(" / ");
}

function onCancel() {
  abortCtl?.abort();
  sending.value = false;
}

function onSubmit(evt: string) {
  const text = (typeof evt === "string" ? evt : inputValue.value).trim();
  if (!text || sending.value) return;
  inputValue.value = "";
  const conv = current.value;
  if (conv.title === "新对话") conv.title = text.slice(0, 18);
  conv.messages.push({ from: "user", content: text, thinking: "", steps: [] });
  void askBackend(conv, text);
}

async function scrollDown() {
  await nextTick();
  const el = (msgBox.value as { $el?: HTMLElement } | HTMLElement | null);
  const node = el && "$el" in (el as object) ? (el as { $el: HTMLElement }).$el : (el as HTMLElement | null);
  if (node) node.scrollTop = node.scrollHeight;
}

async function askBackend(conv: Conversation, text: string) {
  sending.value = true;
  conv.messages.push({ from: "model", content: "", thinking: "", loading: true, steps: [], thinkOpen: true, stepsOpen: true });
  const bot = conv.messages[conv.messages.length - 1];
  await scrollDown();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, conversation_id: conv.id }),
    });
    if (!res.ok) throw new Error(`chat ${res.status}`);
    const { session_id } = (await res.json()) as { session_id: string };

    abortCtl = new AbortController();
    await consumeSSE(`/api/stream/${session_id}`, {
      onEvent: (event, data) => {
        if (event === "status") {
          bot.loading = true;
        } else if (event === "think") {
          bot.loading = false;
          bot.thinking += (data as { content: string }).content || "";
        } else if (event === "tool_call") {
          bot.loading = false;
          bot.steps.push({ tool: data.tool, phase: "call", args: data.args });
        } else if (event === "tool_result") {
          bot.steps.push({ tool: data.tool, phase: "result", text: data.text });
        } else if (event === "delta") {
          bot.loading = false;
          bot.content += (data as { content: string }).content || "";
        } else if (event === "done") {
          bot.loading = false;
          bot.thinkOpen = false;
          bot.stepsOpen = false;
        }
        void scrollDown();
      },
      onError: (err) => {
        bot.loading = false;
        if (err.name !== "AbortError") bot.content = err.message;
      },
    }, abortCtl.signal);
  } catch (err) {
    bot.loading = false;
    if (err instanceof Error && err.name === "AbortError") return;
    bot.content = err instanceof Error ? err.message : "请求失败";
  } finally {
    bot.loading = false;
    sending.value = false;
  }
}
</script>

<style>
.page {
  display: flex;
  height: 100%;
  gap: 12px;
  padding: 12px;
}

.sider {
  width: 220px;
  flex: 0 0 220px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #fff;
  border: 1px solid #d7dbe3;
  border-radius: 16px;
  padding: 12px;
}

.new-btn {
  border: 1px solid #ffd4c6;
  background: #fff1ea;
  color: #c2410c;
  border-radius: 10px;
  padding: 8px 10px;
  cursor: pointer;
  font-size: 14px;
}

.conv-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow: auto;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 4px;
  border-radius: 8px;
  padding: 4px 6px;
  color: #4a5568;
}

.conv-item.on {
  background: #eaf2ff;
  color: #1d4ed8;
}

.conv-title {
  flex: 1 1 auto;
  min-width: 0;
  text-align: left;
  border: none;
  background: transparent;
  cursor: pointer;
  color: inherit;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding: 4px;
}

.conv-del {
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  border-radius: 6px;
  font-size: 16px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.conv-del:hover {
  background: #fee2e2;
  color: #dc2626;
}

.shell {
  flex: 1 1 auto;
  min-width: 0;
  height: 100%;
  padding: 12px 16px 16px;
  gap: 8px;
  background: #fff;
  border: 1px solid #d7dbe3;
  border-radius: 16px;
}

.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.messages {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: auto;
}

.bot-turn {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.think {
  margin-left: 44px;
  padding: 8px 12px;
  border-radius: 10px;
  background: #f7f5ff;
  border: 1px solid #e4ddff;
  font-size: 13px;
  color: #5b4b8a;
}

.think summary {
  cursor: pointer;
  font-weight: 600;
}

.think pre {
  margin: 8px 0 0;
  white-space: pre-wrap;
  font-family: inherit;
  line-height: 1.55;
}

.tool-trace {
  margin-left: 44px;
  padding: 8px 12px;
  border-radius: 10px;
  background: #f5f8ff;
  border: 1px solid #e2e9fb;
  font-size: 13px;
  color: #4a5568;
}

.tool-trace summary {
  cursor: pointer;
  font-weight: 600;
  color: #2b3a55;
}

.tool-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}

.tool-step {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 10px;
  background: #f5f8ff;
  border: 1px solid #e2e9fb;
  font-size: 13px;
  line-height: 1.5;
  color: #4a5568;
  white-space: pre-wrap;
}

.tool-step.calc_penalty {
  background: #f1fbf6;
  border-color: #cfeede;
}

.tool-badge {
  flex: 0 0 auto;
  font-weight: 600;
  color: #2b3a55;
}

.tool-text { color: #5b6776; }

.hint {
  font-size: 12px;
  color: #71757f;
}
</style>
