import React, { useEffect, useMemo, useState } from "react";
import Navbar from "../components/Navbar";
import { useAuth } from "../context/AuthContext";
import { toast } from "react-toastify";

const Message = ({ role, content }) => {
  const isUser = role === "user";

  return (
    <div className={`flex w-full mb-5 ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[78%] rounded-2xl px-4 py-3 whitespace-pre-wrap leading-relaxed ${
          isUser
            ? "bg-purple-600 text-white rounded-br-sm"
            : "bg-gray-100 text-gray-800 rounded-bl-sm"
        }`}
      >
        {content}
      </div>
    </div>
  );
};

const MainPage = () => {
  const { user, API_URL } = useAuth();

  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const activeConversation = useMemo(
    () => conversations.find((item) => item.id === activeConversationId),
    [conversations, activeConversationId]
  );

  const loadConversations = async () => {
    const response = await fetch(`${API_URL}/conversations`, {
      credentials: "include",
    });

    if (!response.ok) {
      throw new Error("Unable to load chat history");
    }

    const data = await response.json();
    setConversations(data.conversations);
    return data.conversations;
  };

  const loadMessages = async (conversationId) => {
    const response = await fetch(
      `${API_URL}/conversations/${conversationId}/messages`,
      { credentials: "include" }
    );

    if (!response.ok) {
      throw new Error("Unable to load conversation");
    }

    const data = await response.json();
    setMessages(data.messages);
  };

  useEffect(() => {
    const initialize = async () => {
      try {
        const list = await loadConversations();

        if (list.length > 0) {
          const latest = list[0];
          setActiveConversationId(latest.id);
          await loadMessages(latest.id);
        }
      } catch (error) {
        toast.error(error.message);
      }
    };

    initialize();
  }, []);

  const createNewChat = async () => {
    try {
      const response = await fetch(`${API_URL}/conversations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ title: "New Chat" }),
      });

      if (!response.ok) {
        throw new Error("Unable to create a new chat");
      }

      const data = await response.json();
      setConversations((prev) => [data.conversation, ...prev]);
      setActiveConversationId(data.conversation.id);
      setMessages([]);
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleSelectConversation = async (conversationId) => {
    try {
      setActiveConversationId(conversationId);
      await loadMessages(conversationId);
    } catch (error) {
      toast.error(error.message);
    }
  };

  const deleteConversation = async (conversationId) => {
    try {
      const response = await fetch(
        `${API_URL}/conversations/${conversationId}`,
        {
          method: "DELETE",
          credentials: "include",
        }
      );

      if (!response.ok) {
        throw new Error("Unable to delete chat");
      }

      const remaining = conversations.filter((item) => item.id !== conversationId);
      setConversations(remaining);

      if (activeConversationId === conversationId) {
        if (remaining.length > 0) {
          setActiveConversationId(remaining[0].id);
          await loadMessages(remaining[0].id);
        } else {
          setActiveConversationId(null);
          setMessages([]);
        }
      }
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const cleanQuery = query.trim();

    if (!cleanQuery || isLoading) return;

    setIsLoading(true);
    setQuery("");

    // Optimistic UI message.
    setMessages((prev) => [
      ...prev,
      {
        id: `temp-user-${Date.now()}`,
        role: "user",
        content: cleanQuery,
      },
    ]);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          query: cleanQuery,
          conversation_id: activeConversationId,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Unable to generate response");
      }

      const data = await response.json();

      setActiveConversationId(data.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          id: `temp-bot-${Date.now()}`,
          role: "assistant",
          content: data.response,
        },
      ]);

      // Keep sidebar title/order in sync with backend.
      setConversations((prev) => {
        const withoutCurrent = prev.filter(
          (item) => item.id !== data.conversation.id
        );
        return [data.conversation, ...withoutCurrent];
      });
    } catch (error) {
      toast.error(error.message);
      setMessages((prev) => prev.slice(0, -1));
      setQuery(cleanQuery);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full min-h-screen bg-gray-100">
      <Navbar solidBackground={true} />

      <div className="pt-[80px] h-screen flex">
        {/* Sidebar */}
        <aside
          className={`${
            isSidebarOpen ? "w-72" : "w-0"
          } bg-gray-900 text-white transition-all duration-300 overflow-hidden flex-shrink-0`}
        >
          <div className="w-72 h-full flex flex-col">
            <div className="p-4 border-b border-gray-700">
              <button
                onClick={createNewChat}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-600 hover:bg-gray-800 transition"
              >
                <span className="text-xl">＋</span>
                <span className="font-medium">New chat</span>
              </button>
            </div>

            <div className="px-4 py-3 text-xs uppercase tracking-wider text-gray-400">
              Your chats
            </div>

            <div className="flex-1 overflow-y-auto px-2 pb-4">
              {conversations.length === 0 ? (
                <p className="text-sm text-gray-500 px-3 py-4">
                  Your saved conversations will appear here.
                </p>
              ) : (
                conversations.map((conversation) => (
                  <div
                    key={conversation.id}
                    className={`group flex items-center gap-2 mb-1 rounded-lg ${
                      activeConversationId === conversation.id
                        ? "bg-gray-800"
                        : "hover:bg-gray-800"
                    }`}
                  >
                    <button
                      onClick={() => handleSelectConversation(conversation.id)}
                      className="flex-1 text-left px-3 py-3 min-w-0"
                    >
                      <p className="truncate text-sm">{conversation.title}</p>
                    </button>

                    <button
                      onClick={() => deleteConversation(conversation.id)}
                      className="opacity-0 group-hover:opacity-100 px-2 text-gray-400 hover:text-red-400 transition"
                      title="Delete chat"
                    >
                      ×
                    </button>
                  </div>
                ))
              )}
            </div>

            <div className="p-4 border-t border-gray-700 text-sm text-gray-300 truncate">
              👤 {user?.name}
            </div>
          </div>
        </aside>

        {/* Main chat */}
        <main className="flex-1 flex flex-col min-w-0">
          <div className="h-14 border-b bg-white flex items-center gap-3 px-4">
            <button
              onClick={() => setIsSidebarOpen((prev) => !prev)}
              className="text-gray-600 hover:text-black text-xl"
              title="Toggle chat history"
            >
              ☰
            </button>

            <div>
              <h1 className="font-semibold text-gray-900">
                {activeConversation?.title || "HealthChatbot"}
              </h1>
              <p className="text-xs text-gray-500">Healthcare assistant</p>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-4 md:px-10 py-6">
            <div className="max-w-3xl mx-auto">
              {messages.length === 0 ? (
                <div className="h-full min-h-[400px] flex items-center justify-center text-center">
                  <div>
                    <div className="text-5xl mb-4">🩺</div>
                    <h2 className="text-2xl font-semibold text-gray-800">
                      How can I help you, {user?.name}?
                    </h2>
                    <p className="text-gray-500 mt-2">
                      Ask a healthcare question to start a new conversation.
                    </p>
                  </div>
                </div>
              ) : (
                messages.map((message) => (
                  <Message
                    key={message.id}
                    role={message.role}
                    content={message.content}
                  />
                ))
              )}

              {isLoading && (
                <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
                  <span className="animate-pulse">●</span>
                  <span>Thinking...</span>
                </div>
              )}
            </div>
          </div>

          <div className="bg-gray-100 px-4 md:px-10 pb-5">
            <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
              <div className="relative">
                <input
                  type="text"
                  placeholder="Message HealthChatbot..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="w-full px-5 py-4 pr-14 rounded-2xl border border-gray-300 bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-300"
                  disabled={isLoading}
                />

                <button
                  type="submit"
                  disabled={isLoading || !query.trim()}
                  className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-purple-600 text-white disabled:bg-gray-300"
                  title="Send"
                >
                  ↑
                </button>
              </div>

              <p className="text-xs text-gray-500 text-center mt-2">
                HealthChatbot can make mistakes. For urgent symptoms, contact a medical professional.
              </p>
            </form>
          </div>
        </main>
      </div>
    </div>
  );
};

export default MainPage;
