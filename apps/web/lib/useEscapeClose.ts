"use client";

import { useEffect, useRef } from "react";

/**
 * 弹窗 ESC 关闭的共享 Hook。
 *
 * 设计要点：
 * 1. 栈式响应——多个弹窗叠加时（例如管理页表单上再弹确认框），
 *    只有最后挂载的那个（栈顶）响应 ESC，避免一次按键关掉整摞弹窗。
 * 2. 输入法保护——中文拼音候选框打开时按 ESC 是「取消候选」，
 *    此时不能关闭弹窗，通过 event.isComposing 拦截。
 * 3. onClose 通过 ref 读取，避免调用方传入内联箭头函数导致
 *    effect 反复重建、打乱弹窗栈顺序。
 */

// 模块级弹窗栈：后挂载的在末尾
const escapeStack: Array<() => void> = [];

export function useEscapeClose(onClose?: () => void, enabled: boolean = true) {
  const callbackRef = useRef<(() => void) | undefined>(onClose);

  // 每次渲染同步最新回调，但不触发下面的 effect 重建
  useEffect(() => {
    callbackRef.current = onClose;
  });

  useEffect(() => {
    if (!enabled) return;

    const entry = () => callbackRef.current?.();
    escapeStack.push(entry);

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      // 输入法组合输入中（如中文拼音候选框），ESC 交给输入法处理
      if (event.isComposing || event.keyCode === 229) return;
      // 只有栈顶弹窗响应
      if (escapeStack[escapeStack.length - 1] !== entry) return;

      event.stopPropagation();
      entry();
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      const index = escapeStack.indexOf(entry);
      if (index >= 0) escapeStack.splice(index, 1);
    };
  }, [enabled]);
}
