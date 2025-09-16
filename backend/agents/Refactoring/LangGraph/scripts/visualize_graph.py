"""
Extract and visualize the LangGraph Currency Agent structure
"""

import os
from app.agent import CurrencyAgent

# Set dummy API key for visualization
os.environ['GOOGLE_API_KEY'] = 'dummy_key_for_visualization'

def main():
    print("=== LangGraph Currency Agent Visualization ===")

    # Initialize the agent
    try:
        agent = CurrencyAgent()
        graph = agent.graph

        print("\n1. Graph Nodes:")
        nodes = graph.get_graph().nodes
        for i, node in enumerate(nodes, 1):
            print(f"   {i}. {node}")

        print("\n2. Graph Edges:")
        edges = graph.get_graph().edges
        for i, edge in enumerate(edges, 1):
            print(f"   {i}. {edge[0]} -> {edge[1]}")

        print("\n3. Graph Configuration:")
        print(f"   - Number of Nodes: {len(nodes)}")
        print(f"   - Number of Edges: {len(edges)}")
        try:
            print(f"   - Entry Point: {graph.get_graph().entry_point}")
        except:
            print("   - Entry Point: __start__ (default)")

        print("\n4. ASCII Graph Representation:")
        try:
            ascii_graph = graph.get_graph().draw_ascii()
            print(ascii_graph)
        except Exception as e:
            print(f"ASCII drawing not available: {e}")

        print("\n5. Mermaid Graph Definition:")
        try:
            mermaid = graph.get_graph().draw_mermaid()
            print(mermaid)

            # Save mermaid to file for web visualization
            with open("currency_agent_graph.mmd", "w") as f:
                f.write(mermaid)
            print("\nMermaid graph saved to currency_agent_graph.mmd")

        except Exception as e:
            print(f"Mermaid drawing not available: {e}")

        print("\n6. Generate PNG (if possible):")
        try:
            png_data = graph.get_graph().draw_mermaid_png()
            with open("currency_agent_graph.png", "wb") as f:
                f.write(png_data)
            print("PNG graph saved to currency_agent_graph.png")
        except Exception as e:
            print(f"PNG generation not available: {e}")

    except Exception as e:
        print(f"Error initializing agent: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()