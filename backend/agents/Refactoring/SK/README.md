
# Multi-Agent System with Semantic Kernel and Google A2A

This repository contains the code reference for building a multi-agent system that demonstrates seamless collaboration between agents built with **Microsoft Semantic Kernel** and communicating via **Google Agent-to-Agent (A2A) protocol**.

The project showcases a practical example: a **Trip Management System** where a `Travel Planner Agent` orchestrates a `Flight Booking Agent` to assist users with their travel needs.

-----

## 🌟 Features

  * **Multi-Agent Collaboration:** See how independent agents can work together using a common communication protocol.
  * **Microsoft Semantic Kernel Integration:** Agents are built leveraging Semantic Kernel's powerful capabilities for AI orchestration and tool use.
  * **Google A2A Protocol:** Demonstrates how to set up A2A servers and clients for robust agent-to-agent communication.
  * **Modular Design:** Each agent is independent, with its own toolset and runtime, promoting scalability and maintainability.
  * **Stateful Interactions:** Agents maintain context for multi-turn conversations using `context_id`.

-----

## 🚀 Project Structure

This project is divided into two main parts:

1.  **A2A Agent Server (`flight-booking-agent`):** Hosts the `Flight Booking Agent`.
2.  **A2A Client (`travel-planner-agent`):** Hosts the `Travel Planner Agent` which acts as the orchestrator and consumes the `Flight Booking Agent` as a tool.

The core components and their roles are detailed in the [accompanying blog post](https://www.google.com/search?q=YOUR_BLOG_POST_LINK_HERE).

```
.
├── flight_booking_agent_server/
│   ├── __main__.py          # A2A Server implementation for Flight Booking Agent
│   └── flight_booking_agent.py # Defines the SemanticKernelFlightBookingAgent
├── travel_planner_agent_client/
│   ├── travel_agent.py      # A2A Client implementation for Travel Planner Agent
│   └── flight_booking_tool.py # Semantic Kernel tool to interact with Flight Booking Agent
├── requirements.txt         # Project dependencies
└── README.md                # You are here!
```

-----

## 🛠️ Setup and Installation

### Prerequisites

Before you begin, ensure you have the following:

  * Python 3.9+
  * An OpenAI API key (from https://platform.openai.com/api-keys) with access to chat completion models (e.g., `gpt-3.5-turbo`, `gpt-4`).
  * `uvicorn` (for running the A2A server).

### Installation Steps

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
    cd YOUR_REPO_NAME
    ```

2.  **Create a virtual environment (recommended):**

    ```bash
    python -m venv venv
    source venv/bin/activate # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure API Keys:**

      * **Method 1 (Recommended): Environment Variable**
        Set your OpenAI API key as an environment variable:
        ```bash
        # On Windows
        set OPENAI_API_KEY=your-openai-api-key-here
        
        # On macOS/Linux
        export OPENAI_API_KEY=your-openai-api-key-here
        ```

      * **Method 2: Direct Code Modification**
        If you prefer, you can directly replace the placeholders in the code:
        - In `SemanticKernel-FlightBookingAgentServer/agent.py`: Replace `<your-openai-api-key>`
        - In `SemanticKernel-TravelBookingAgent/travel-agent.py`: Replace `<your-openai-api-key>`

      * **Note:** The code is now configured to use OpenAI's API instead of Azure OpenAI. Make sure you have sufficient credits in your OpenAI account.

-----

## 🏃 How to Run

To see the multi-agent system in action, you'll need to run the A2A server and client in separate terminals.

1.  **Start the Flight Booking Agent (A2A Server):**
    Open your first terminal, navigate to the project root, and run:

    ```bash
    cd SemanticKernel-FlightBookingAgentServer
    python __main__.py
    ```

    You should see output indicating the server is starting on `http://0.0.0.0:9999`.

2.  **Start the Travel Planner Agent (A2A Client):**
    Open a *second* terminal, navigate to the project root, and run:

    ```bash
    cd SemanticKernel-TravelBookingAgent
    python travel-agent.py
    ```

    This will start the `Travel Planner Agent` on `http://0.0.0.0:8000`. Open your browser and go to `http://localhost:8000` to interact with the chat interface.

-----

## 💡 How it Works

When you interact with the `Travel Planner Agent` (the A2A client), it will intelligently determine if a user query requires flight booking assistance. If it does, it will:

1.  Invoke its internal `FlightBookingTool`.
2.  The `FlightBookingTool` will act as an A2A client, fetching the `AgentCard` from the `Flight Booking Agent` (A2A server).
3.  It will then send a `SendMessageRequest` to the `Flight Booking Agent` with the user's flight booking request.
4.  The `Flight Booking Agent` processes the request and sends back a response, which the `Travel Planner Agent` then relays back to the user.

Both agents maintain their own conversational context based on a `context_id`, demonstrating stateful interactions within this multi-agent setup.

-----

## 📚 Learn More

  * **Microsoft Semantic Kernel Documentation:** [https://learn.microsoft.com/en-us/semantic-kernel/](https://learn.microsoft.com/en-us/semantic-kernel/)
  * **Google Agent-to-Agent (A2A) Documentation:** [https://developers.google.com/agents/docs/a2a](https://www.google.com/search?q=https://developers.google.com/agents/docs/a2a)
  * **My Blog Post:** [https://www.google.com/search?q=YOUR\_BLOG\_POST\_LINK\_HERE] (Highly recommended for a detailed explanation of the steps\!)

-----

## 🙏 Contributing

Contributions are welcome\! If you have suggestions or improvements, please open an issue or submit a pull request.

-----
