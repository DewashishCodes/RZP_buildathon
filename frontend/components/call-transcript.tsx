"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PhoneIcon, PlayIcon, StopIcon } from "./icons";

interface Turn {
  role: "agent" | "customer";
  text: string;
}

/**
 * Parses the stored transcript format ("Agent: ...\nCustomer: ...", one
 * turn per line-prefix) into ordered turns. Continuation lines without a
 * role prefix stay attached to the previous turn.
 */
function parseTranscript(raw: string): Turn[] {
  const turns: Turn[] = [];
  for (const line of raw.split("\n")) {
    const match = line.match(/^(agent|customer)\s*:\s*(.*)$/i);
    if (match) {
      turns.push({ role: match[1].toLowerCase() as Turn["role"], text: match[2] });
    } else if (line.trim() && turns.length > 0) {
      turns[turns.length - 1].text += `\n${line}`;
    }
  }
  return turns;
}

export function CallTranscript({ transcript }: { transcript: string }) {
  const [open, setOpen] = useState(false);
  const [speakingIndex, setSpeakingIndex] = useState<number | null>(null);
  const turns = useMemo(() => parseTranscript(transcript), [transcript]);
  const speakingRef = useRef(false);
  // Feature-detect at use time rather than in an effect: this component's
  // interactive parts render client-side only (behind the open toggle), so
  // there's no hydration concern.
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;

  useEffect(() => {
    return () => {
      if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    };
  }, []);

  const stop = useCallback(() => {
    speakingRef.current = false;
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    setSpeakingIndex(null);
  }, []);

  /**
   * Plays the agent's turns in sequence via the Web Speech API - the
   * zero-cost stand-in for the PRD's deferred Sarvam TTS stretch goal.
   * Prefers a Hindi voice for Hinglish flavor, falls back to whatever the
   * browser offers; customer turns are skipped (the judge reads those).
   */
  const play = useCallback(() => {
    if (!supported || turns.length === 0) return;
    speakingRef.current = true;

    const pickVoice = (): SpeechSynthesisVoice | null => {
      const voices = window.speechSynthesis.getVoices();
      return (
        voices.find((v) => v.lang.toLowerCase().startsWith("hi")) ??
        voices.find((v) => v.lang.toLowerCase() === "en-in") ??
        null
      );
    };

    const agentTurns = turns.map((t, i) => ({ ...t, index: i })).filter((t) => t.role === "agent");
    let cursor = 0;

    const speakNext = () => {
      if (!speakingRef.current || cursor >= agentTurns.length) {
        stop();
        return;
      }
      const turn = agentTurns[cursor++];
      const utterance = new SpeechSynthesisUtterance(turn.text.replace(/\n/g, " "));
      const voice = pickVoice();
      if (voice) utterance.voice = voice;
      utterance.rate = 0.95;
      utterance.onend = () => {
        if (speakingRef.current) setTimeout(speakNext, 350);
      };
      utterance.onerror = stop;
      setSpeakingIndex(turn.index);
      window.speechSynthesis.speak(utterance);
    };

    // Voices may not be loaded on first use; getVoices() returning [] is
    // handled by pickVoice()'s ?? null fallback at speak time.
    speakNext();
  }, [supported, turns, stop]);

  const playing = speakingIndex !== null;

  return (
    <div className="mt-3">
      <div className="flex items-center justify-between">
        <button
          onClick={() => {
            if (playing) stop();
            setOpen(!open);
          }}
          aria-expanded={open}
          className="flex cursor-pointer items-center gap-1.5 text-xs text-text-muted hover:text-text-secondary"
        >
          <PhoneIcon className="h-3 w-3" aria-hidden="true" />
          {open ? "Hide call transcript" : "View call transcript"}
        </button>
        {open && supported && (
          <button
            onClick={playing ? stop : play}
            className="inline-flex items-center gap-1 rounded-full border border-border-strong px-2.5 py-1 text-xs font-medium text-text-primary transition-colors hover:bg-surface-2"
          >
            {playing ? <StopIcon className="h-3 w-3" /> : <PlayIcon className="h-3 w-3" />}
            {playing ? "Stop playback" : "Play agent audio"}
          </button>
        )}
      </div>

      {open && (
        <div className="mt-3 flex flex-col gap-2">
          {turns.length === 0 && <p className="text-xs text-text-muted">(empty transcript)</p>}
          {turns.map((turn, i) => (
            <div
              key={i}
              className={`flex ${turn.role === "customer" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-xl px-3.5 py-2 text-xs leading-relaxed whitespace-pre-wrap ${
                  turn.role === "customer"
                    ? "rounded-br-sm bg-accent/15 text-text-primary"
                    : `rounded-bl-sm border border-border bg-surface-2 text-text-secondary ${
                        speakingIndex === i ? "ring-1 ring-accent" : ""
                      }`
                }`}
              >
                <span className="mb-0.5 block text-[10px] font-medium uppercase tracking-wide text-text-muted">
                  {turn.role}
                </span>
                {turn.text}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
