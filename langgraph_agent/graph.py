from langgraph.graph import StateGraph # type: ignore
from langgraph_agent.schema import ConversationState
from langgraph_agent.nodes import *
from langgraph.graph import END # type: ignore

def build_graph():
    graph = StateGraph(ConversationState)

    graph.add_node("detect_intent", validate_and_extract_node)
    graph.add_node("confirm_booking", confirm_booking_node)
    graph.add_node("confirm_cancellation", confirm_cancellation_node)
    graph.add_node("confirm_reschedule", confirm_reschedule_node)
    graph.add_node("back_to_top", back_to_top_node)
    graph.add_node("completion_node", completion_node)
    graph.add_node("error_node", error_node)
    graph.add_node("reschedule_all_for_doctor", confirm_reschedule_all_for_doctor_node)

    graph.set_entry_point("detect_intent")
    
    graph.add_conditional_edges("detect_intent", lambda s: s["stage"], {
        "confirm_booking": "confirm_booking",
        "confirm_cancellation": "confirm_cancellation",
        "confirm_reschedule": "confirm_reschedule",
        "confirm_reschedule_all_for_doctor" : "reschedule_all_for_doctor",
        "INCOMPLETE_INFO": "back_to_top",
        "error": "error_node",
        "done": "completion_node"
    })
    
    graph.add_edge("confirm_booking", "completion_node")
    graph.add_edge("confirm_cancellation", "completion_node")
    graph.add_edge("confirm_reschedule", "completion_node")
    graph.add_edge("reschedule_all_for_doctor", "completion_node")
    
    graph.add_edge("back_to_top", END)
    
    return graph.compile()








