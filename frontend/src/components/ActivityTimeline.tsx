import {
  Loader2,
  Activity,
  Info,
  Search,
  TextSearch,
  Brain,
  Pen,
  ChevronDown,
  ChevronUp,
  Code2, // Icon for Coding
  FileText, // Icon for General/Output
  Link as LinkIcon, // Icon for Sources
} from "lucide-react";
import { useState, useMemo } from "react";
import { Badge } from "@/components/ui/badge"; // For source links

export interface ProcessedEvent {
  title: string;
  data: any;
  sectionType: string; // e.g., "Planning", "Searching", "Coding", "Finalizing"
  isSources?: boolean; // True if data contains source links
}

interface ActivityTimelineProps {
  processedEvents: ProcessedEvent[];
  isLoading: boolean;
}

// Helper to get icon based on sectionType
const getSectionIcon = (sectionType: string) => {
  switch (sectionType.toLowerCase()) {
    case "querying":
      return <TextSearch className="h-5 w-5 mr-2 text-neutral-400" />;
    case "searching":
      return <Search className="h-5 w-5 mr-2 text-neutral-400" />;
    case "planning":
      return <Brain className="h-5 w-5 mr-2 text-neutral-400" />;
    case "coding":
      return <Code2 className="h-5 w-5 mr-2 text-neutral-400" />;
    case "finalizing":
      return <Pen className="h-5 w-5 mr-2 text-neutral-400" />;
    default:
      return <Activity className="h-5 w-5 mr-2 text-neutral-400" />;
  }
};

export function ActivityTimeline({
  processedEvents,
  isLoading,
}: ActivityTimelineProps) {
  const [expandedSections, setExpandedSections] = useState<
    Record<string, boolean>
  >({});

  const groupedEvents = useMemo(() => {
    return processedEvents.reduce((acc, event) => {
      const { sectionType } = event;
      if (!acc[sectionType]) {
        acc[sectionType] = [];
      }
      acc[sectionType].push(event);
      return acc;
    }, {} as Record<string, ProcessedEvent[]>);
  }, [processedEvents]);

  // Automatically expand new sections as they appear, unless manually collapsed
  useMemo(() => {
    Object.keys(groupedEvents).forEach(sectionType => {
      if (expandedSections[sectionType] === undefined) {
        setExpandedSections(prev => ({...prev, [sectionType]: true}));
      }
    });
  }, [groupedEvents, expandedSections]);


  const toggleSection = (sectionType: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [sectionType]: !prev[sectionType],
    }));
  };

  if (isLoading && processedEvents.length === 0) {
    return (
      <div className="p-4 text-sm text-neutral-400 flex items-center">
        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
        Processing...
      </div>
    );
  }

  if (!isLoading && processedEvents.length === 0) {
    return (
      <div className="p-4 text-sm text-neutral-500 flex flex-col items-center text-center">
        <Info className="h-5 w-5 mb-1" />
        No activity to display.
      </div>
    );
  }

  return (
    <div className="p-1 space-y-2 bg-neutral-800 rounded-lg">
      {Object.entries(groupedEvents).map(([sectionType, events]) => (
        <div key={sectionType} className="rounded-md">
          <button
            onClick={() => toggleSection(sectionType)}
            className="w-full flex items-center justify-between p-2 bg-neutral-700 hover:bg-neutral-600 rounded-t-md focus:outline-none transition-colors duration-150"
          >
            <div className="flex items-center text-sm font-medium text-neutral-100">
              {getSectionIcon(sectionType)}
              {sectionType} ({events.length})
            </div>
            {expandedSections[sectionType] ? (
              <ChevronUp className="h-4 w-4 text-neutral-400" />
            ) : (
              <ChevronDown className="h-4 w-4 text-neutral-400" />
            )}
          </button>
          {expandedSections[sectionType] && (
            <div className="p-2 space-y-1 bg-neutral-750 rounded-b-md">
              {events.map((event, index) => (
                <div key={index} className="text-xs text-neutral-300 p-1.5 rounded bg-neutral-800">
                  <p className="font-medium text-neutral-200 break-all">
                    {event.title}
                  </p>
                  {event.isSources && Array.isArray(event.data) ? (
                    <div className="mt-1 space-y-0.5">
                      {event.data.map(
                        (source: any, idx: number) =>
                          source.url && (
                            <a
                              key={idx}
                              href={source.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center text-blue-400 hover:text-blue-300 hover:underline"
                            >
                              <LinkIcon className="h-3 w-3 mr-1 flex-shrink-0" />
                              <span className="truncate">
                                {source.title || source.url}
                              </span>
                            </a>
                          )
                      )}
                    </div>
                  ) : typeof event.data === "string" ? (
                    <p className="whitespace-pre-wrap break-all">{event.data}</p>
                  ) : event.data && (typeof event.data.stdout === 'string' || typeof event.data.stderr === 'string' || typeof event.data.error === 'string') ? (
                    // Handle code execution output object
                    <>
                      {event.data.stdout && <pre className="whitespace-pre-wrap bg-black p-1 rounded mt-1 text-green-400 break-all">STDOUT: {event.data.stdout}</pre>}
                      {event.data.stderr && <pre className="whitespace-pre-wrap bg-black p-1 rounded mt-1 text-red-400 break-all">STDERR: {event.data.stderr}</pre>}
                      {event.data.error && <pre className="whitespace-pre-wrap bg-black p-1 rounded mt-1 text-red-500 break-all">ERROR: {event.data.error}</pre>}
                    </>
                  ) : (
                    <pre className="whitespace-pre-wrap text-xs break-all">
                      {JSON.stringify(event.data, null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
      {isLoading && (
         <div className="p-2 text-xs text-neutral-400 flex items-center bg-neutral-700 rounded-md mt-2">
            <Loader2 className="h-3 w-3 mr-2 animate-spin" />
            Agent is thinking...
        </div>
      )}
    </div>
  );
}
