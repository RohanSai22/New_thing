import { useStream } from "@langchain/langgraph-sdk/react";
import type { Message } from "@langchain/langgraph-sdk";
import { useState, useEffect, useRef, useCallback } from "react";
import { ProcessedEvent } from "@/components/ActivityTimeline";
import { WelcomeScreen } from "@/components/WelcomeScreen";
import { ChatMessagesView } from "@/components/ChatMessagesView";

export default function App() {
  const [processedEventsTimeline, setProcessedEventsTimeline] = useState<
    ProcessedEvent[]
  >([]);
  const [historicalActivities, setHistoricalActivities] = useState<
    Record<string, ProcessedEvent[]>
  >({});
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const hasFinalizeEventOccurredRef = useRef(false);

  const thread = useStream<{
    messages: Message[];
    initial_search_query_count: number;
    max_research_loops: number;
    reasoning_model: string;
    effort: string; // Add this line
  }>({
    apiUrl: import.meta.env.DEV
      ? "http://localhost:2024"
      : "http://localhost:8123",
    assistantId: "agent",
    messagesKey: "messages",
    onFinish: (event: any) => {
      console.log(event);
    },
    onUpdateEvent: (event: any) => {
      let newProcessedEvents: ProcessedEvent[] = [];
      console.log("Raw event:", event); // For debugging

      for (const nodeName in event) {
        const nodeEvent = event[nodeName]; // This is the {type: "...", data: "..."} object
        if (nodeEvent && typeof nodeEvent === 'object' && nodeEvent.type) {
          let sectionType = "General"; // Default section type
          let title = nodeName.replace(/_/g, ' '); // Default title from node name
          title = title.charAt(0).toUpperCase() + title.slice(1); // Capitalize
          let isSources = false;
          let data = nodeEvent.data;

          // Determine sectionType and customize title based on nodeName and eventType
          if (nodeName === "generate_query") {
            sectionType = "Querying";
            title = "Generating Search Queries";
          } else if (nodeName === "web_research") {
            sectionType = "Searching";
            if (nodeEvent.type === "status") {
              title = "Web Research Status";
            } else if (nodeEvent.type === "sources") {
              title = "Found Sources";
              isSources = true; // Mark that data is source links
            }
          } else if (nodeName === "reflection") {
            sectionType = "Planning";
            if (nodeEvent.type === "status") {
              title = "Reflection Status";
            } else if (nodeEvent.type === "plan") {
              title = "Reflection Plan";
            }
          } else if (nodeName === "code_execution") {
            sectionType = "Coding";
            if (nodeEvent.type === "status") {
              title = "Code Execution Status";
            } else if (nodeEvent.type === "output") {
              title = "Code Execution Output";
              // Data for code output might be an object {stdout, stderr, error}
              // Or it could be a simple string. ActivityTimeline will need to handle this.
            }
          } else if (nodeName === "finalize_answer") {
            sectionType = "Finalizing";
            title = "Finalizing Answer";
            hasFinalizeEventOccurredRef.current = true; // Keep existing logic for finalize
          }

          newProcessedEvents.push({
            title: title,
            data: data,
            sectionType: sectionType,
            isSources: isSources,
          });
        }
      }

      if (newProcessedEvents.length > 0) {
        setProcessedEventsTimeline((prevEvents) => [
          ...prevEvents,
          ...newProcessedEvents,
        ]);
      }
    },
  });

  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollViewport = scrollAreaRef.current.querySelector(
        "[data-radix-scroll-area-viewport]"
      );
      if (scrollViewport) {
        scrollViewport.scrollTop = scrollViewport.scrollHeight;
      }
    }
  }, [thread.messages]);

  useEffect(() => {
    if (
      hasFinalizeEventOccurredRef.current &&
      !thread.isLoading &&
      thread.messages.length > 0
    ) {
      const lastMessage = thread.messages[thread.messages.length - 1];
      if (lastMessage && lastMessage.type === "ai" && lastMessage.id) {
        setHistoricalActivities((prev) => ({
          ...prev,
          [lastMessage.id!]: [...processedEventsTimeline],
        }));
      }
      hasFinalizeEventOccurredRef.current = false;
    }
  }, [thread.messages, thread.isLoading, processedEventsTimeline]);

  const handleSubmit = useCallback(
    (submittedInputValue: string, effort: string, model: string) => {
      if (!submittedInputValue.trim()) return;
      setProcessedEventsTimeline([]);
      hasFinalizeEventOccurredRef.current = false;

      // convert effort to, initial_search_query_count and max_research_loops
      // low means max 1 loop and 1 query
      // medium means max 3 loops and 3 queries
      // high means max 10 loops and 5 queries
      let initial_search_query_count = 0;
      let max_research_loops = 0;
      switch (effort) {
        case "low":
          initial_search_query_count = 1;
          max_research_loops = 1;
          break;
        case "medium":
          initial_search_query_count = 3;
          max_research_loops = 3;
          break;
        case "high":
          initial_search_query_count = 5;
          max_research_loops = 10;
          break;
      }

      const newMessages: Message[] = [
        ...(thread.messages || []),
        {
          type: "human",
          content: submittedInputValue,
          id: Date.now().toString(),
        },
      ];
      thread.submit({
        messages: newMessages,
        initial_search_query_count: initial_search_query_count,
        max_research_loops: max_research_loops,
        reasoning_model: model,
        effort: effort, // Add this line
      });
    },
    [thread]
  );

  const handleCancel = useCallback(() => {
    thread.stop();
    window.location.reload();
  }, [thread]);

  return (
    <div className="flex h-screen text-neutral-100 font-sans antialiased">
      <main className="flex-1 flex flex-col overflow-hidden max-w-4xl mx-auto w-full">
        <div
          className={`flex-1 overflow-y-auto ${
            thread.messages.length === 0 ? "flex" : ""
          }`}
        >
          {thread.messages.length === 0 ? (
            <WelcomeScreen
              handleSubmit={handleSubmit}
              isLoading={thread.isLoading}
              onCancel={handleCancel}
            />
          ) : (
            <ChatMessagesView
              messages={thread.messages}
              isLoading={thread.isLoading}
              scrollAreaRef={scrollAreaRef}
              onSubmit={handleSubmit}
              onCancel={handleCancel}
              liveActivityEvents={processedEventsTimeline}
              historicalActivities={historicalActivities}
            />
          )}
        </div>
      </main>
    </div>
  );
}
