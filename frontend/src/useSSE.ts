/**
 * useSSE —— 用 fetch + ReadableStream 手写 SSE 解析，专门演示两个「一定会踩的坑」。
 *
 * 为什么不用 EventSource？
 *   EventSource 只支持 GET、不能带请求体、不能自定义头，且看不到分片细节。
 *   高代码课要的是把水管拆开看：所以这里用 fetch 手动读流。
 *
 * 坑一（中文乱码）：TextDecoder 必须 decode(value, { stream: true })。
 *   否则一个汉字的 3 个字节被拆在两个网络分片里时，会各自解码成「�」。
 *
 * 坑二（半行 JSON）：SSE 事件以空行分隔、字段以 \n 分隔，但网络不按行切包。
 *   所以要用一个 buffer 累加，只处理「完整的一段」，最后不完整的半行留到下一轮再拼。
 */

export type SSEHandlers = {
  onEvent: (event: string, data: any) => void;
  onError?: (err: Error) => void;
  onDone?: () => void;
};

export async function consumeSSE(
  url: string,
  handlers: SSEHandlers,
  signal?: AbortSignal,
  headers: Record<string, string> = {},
): Promise<void> {
  const res = await fetch(url, {
    headers: { Accept: "text/event-stream", ...headers },
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`SSE ${res.status}：确认后端 8000 已启动，且 Vite 代理了 /api`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;

      // 坑一修法：stream: true 让解码器在分片边界上保留半个多字节字符
      buffer += decoder.decode(value, { stream: true });

      // 坑二修法：以空行（\n\n）切出「完整事件」，剩下的半个事件留在 buffer
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const rawEvent = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        dispatch(rawEvent, handlers);
      }
    }
    // 冲洗解码器尾部，并处理可能残留的最后一个事件
    buffer += decoder.decode();
    if (buffer.trim()) dispatch(buffer, handlers);
    handlers.onDone?.();
  } catch (err) {
    handlers.onError?.(err instanceof Error ? err : new Error(String(err)));
  } finally {
    reader.releaseLock();
  }
}

function dispatch(rawEvent: string, handlers: SSEHandlers): void {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of rawEvent.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return;
  const dataStr = dataLines.join("\n");
  try {
    handlers.onEvent(event, JSON.parse(dataStr));
  } catch {
    handlers.onEvent(event, dataStr);
  }
}
