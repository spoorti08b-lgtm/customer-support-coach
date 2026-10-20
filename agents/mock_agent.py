class MockAgent:
    """A simple mock agent for customer support testing."""

    def generate_response(self, message: str) -> str:
        if not isinstance(message, str):
            raise TypeError("Customer message must be a string.")

        message = message.strip().lower()

        if not message:
            raise ValueError("Customer message cannot be empty.")

        if "refund" in message or "money back" in message:
            return (
                "I understand you would like a refund. "
                "I'll help you understand the next steps."
            )

        elif any(word in message for word in ["order", "delivery", "shipping"]):
            return (
                "I'm sorry for the inconvenience. "
                "Could you please share your order ID "
                "so I can help check the status?"
            )

        elif any(word in message for word in ["payment", "charged", "billing"]):
            return (
                "I understand your concern about the payment. "
                "Please share the transaction details "
                "so we can investigate the issue."
            )

        elif any(word in message for word in ["angry", "frustrated", "upset"]):
            return (
                "I'm sorry this experience has been frustrating. "
                "I understand your concern and will try to help."
            )

        elif "cancel" in message or "cancellation" in message:
            return (
                "I can help you with your cancellation request. "
                "Could you please provide the relevant order details?"
            )

        else:
            return (
                "Thank you for contacting support. "
                "Could you please provide a few more details "
                "so I can assist you?"
            )


if __name__ == "__main__":
    agent = MockAgent()

    message = input("Enter a customer message: ")
    response = agent.generate_response(message)

    print("\nMock Agent Response:")
    print(response)