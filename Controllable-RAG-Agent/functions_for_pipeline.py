from langchain_openai import ChatOpenAI 
from langchain.vectorstores import  FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser

from langgraph.graph import END, StateGraph

from dotenv import load_dotenv
from pprint import pprint
import os
from typing_extensions import TypedDict
from typing import List, TypedDict

from helper_functions import escape_quotes, text_wrap

"""
Set the environment variables for the API keys.
"""
load_dotenv()
os.environ["PYDEVD_WARN_EVALUATION_TIMEOUT"] = "100000"
os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')

def create_retrievers():
    embeddings = OpenAIEmbeddings()
    chunks_vector_store =  FAISS.load_local("chunks_vector_store", embeddings, allow_dangerous_deserialization=True)
    chapter_summaries_vector_store =  FAISS.load_local("chapter_summaries_vector_store", embeddings, allow_dangerous_deserialization=True)
    book_quotes_vectorstore =  FAISS.load_local("book_quotes_vectorstore", embeddings, allow_dangerous_deserialization=True)

    chunks_query_retriever = chunks_vector_store.as_retriever(search_kwargs={"k": 1})     
    chapter_summaries_query_retriever = chapter_summaries_vector_store.as_retriever(search_kwargs={"k": 1})
    book_quotes_query_retriever = book_quotes_vectorstore.as_retriever(search_kwargs={"k": 10})
    return chunks_query_retriever, chapter_summaries_query_retriever, book_quotes_query_retriever

chunks_query_retriever, chapter_summaries_query_retriever, book_quotes_query_retriever = create_retrievers()

def retrieve_chunks_context_per_question(state):
    print("正在從 Chunks 資料庫檢索...")
    question = state["query_to_retrieve_or_answer"]
    docs = chunks_query_retriever.get_relevant_documents(question)
    context = " ".join(doc.page_content for doc in docs)
    return {"context": escape_quotes(context), "question": question}

def retrieve_summaries_context_per_question(state):
    print("正在從 Summaries 資料庫檢索...")
    question = state["query_to_retrieve_or_answer"]
    docs_summaries = chapter_summaries_query_retriever.get_relevant_documents(question)
    # **修正：使用新的元數據格式**
    context_summaries = " ".join(
        f"{doc.page_content} (來源: {doc.metadata.get('source', '未知')}, 頁數: {doc.metadata.get('page_chunk', 'N/A')})" for doc in docs_summaries
    )
    return {"context": escape_quotes(context_summaries), "question": question}

def retrieve_book_quotes_context_per_question(state):
    print("正在從 Quotes 資料庫檢索...")
    question = state["query_to_retrieve_or_answer"]
    docs_book_quotes = book_quotes_query_retriever.get_relevant_documents(question)
    book_qoutes = " ".join(doc.page_content for doc in docs_book_quotes)
    return {"context": escape_quotes(book_qoutes), "question": question}

# ... (檔案的其餘部分保持不變) ...

# 注意：為了簡潔，此處僅顯示被修改的函數。實際寫入操作將包含檔案的全部內容。
# 以下為檔案的其餘部分，保持原樣。

def create_keep_only_relevant_content_chain():
    keep_only_relevant_content_prompt_template = """you receive a query: {query} and retrieved docuemnts: {retrieved_documents} from a
    vector store.
    You need to filter out all the non relevant information that don't supply important information regarding the {query}.
    your goal is just to filter out the non relevant information.
    you can remove parts of sentences that are not relevant to the query or remove whole sentences that are not relevant to the query.
    DO NOT ADD ANY NEW INFORMATION THAT IS NOT IN THE RETRIEVED DOCUMENTS.
    output the filtered relevant content.
    """


    class KeepRelevantContent(BaseModel):
        relevant_content: str = Field(description="The relevant content from the retrieved documents that is relevant to the query.")


    keep_only_relevant_content_prompt = PromptTemplate(
        template=keep_only_relevant_content_prompt_template,
        input_variables=["query", "retrieved_documents"],
    )


    keep_only_relevant_content_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)
    keep_only_relevant_content_chain = keep_only_relevant_content_prompt | keep_only_relevant_content_llm.with_structured_output(KeepRelevantContent)
    return keep_only_relevant_content_chain

keep_only_relevant_content_chain = create_keep_only_relevant_content_chain()
def keep_only_relevant_content(state):
    question = state["question"]
    context = state["context"]

    input_data = {
    "query": question,
    "retrieved_documents": context
}
    print("keeping only the relevant content...")
    pprint("--------------------")
    output = keep_only_relevant_content_chain.invoke(input_data)
    relevant_content = output.relevant_content
    relevant_content = "".join(relevant_content)
    relevant_content = escape_quotes(relevant_content)

    return {"relevant_context": relevant_content, "context": context, "question": question}

def create_question_answer_from_context_cot_chain():
    class QuestionAnswerFromContext(BaseModel):
        answer_based_on_content: str = Field(description="generates an answer to a query based on a given context.")

    question_answer_from_context_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)


    question_answer_cot_prompt_template = """ 
    Examples of Chain-of-Thought Reasoning

    Example 1

    Context: Mary is taller than Jane. Jane is shorter than Tom. Tom is the same height as David.
    Question: Who is the tallest person?
    Reasoning Chain:
    The context tells us Mary is taller than Jane
    It also says Jane is shorter than Tom
    And Tom is the same height as David
    So the order from tallest to shortest is: Mary, Tom/David, Jane
    Therefore, Mary must be the tallest person

    Example 2
    Context: Harry was reading a book about magic spells. One spell allowed the caster to turn a person into an animal for a short time. Another spell could levitate objects.
    A third spell created a bright light at the end of the caster's wand.
    Question: Based on the context, if Harry cast these spells, what could he do?
    Reasoning Chain:
    The context describes three different magic spells
    The first spell allows turning a person into an animal temporarily
    The second spell can levitate or float objects
    The third spell creates a bright light
    If Harry cast these spells, he could turn someone into an animal for a while, make objects float, and create a bright light source
    So based on the context, if Harry cast these spells he could transform people, levitate things, and illuminate an area
    Instructions.

    Example 3 
    Context: Harry Potter woke up on his birthday to find a present at the end of his bed. He excitedly opened it to reveal a Nimbus 2000 broomstick.
    Question: Why did Harry receive a broomstick for his birthday?
    Reasoning Chain:
    The context states that Harry Potter woke up on his birthday and received a present - a Nimbus 2000 broomstick.
    However, the context does not provide any information about why he received that specific present or who gave it to him.
    There are no details about Harry's interests, hobbies, or the person who gifted him the broomstick.
    Without any additional context about Harry's background or the gift-giver's motivations, there is no way to determine the reason he received a broomstick as a birthday present.

    For the question below, provide your answer by first showing your step-by-step reasoning process, breaking down the problem into a chain of thought before arriving at the final answer,
    just like in the previous examples.
    Context
    {context}
    Question
    {question}
    """

    question_answer_from_context_cot_prompt = PromptTemplate(
        template=question_answer_cot_prompt_template,
        input_variables=["context", "question"],
    )
    question_answer_from_context_cot_chain = question_answer_from_context_cot_prompt | question_answer_from_context_llm.with_structured_output(QuestionAnswerFromContext)
    return question_answer_from_context_cot_chain

question_answer_from_context_cot_chain = create_question_answer_from_context_cot_chain()

def answer_question_from_context(state):
    question = state["question"]
    context = state["aggregated_context"] if "aggregated_context" in state else state["context"]

    input_data = {
    "question": question,
    "context": context
}
    print("Answering the question from the retrieved context...")

    output = question_answer_from_context_cot_chain.invoke(input_data)
    answer = output.answer_based_on_content
    print(f'answer before checking hallucination: {answer}')
    return {"answer": answer, "context": context, "question": question}

def create_is_relevant_content_chain():

    is_relevant_content_prompt_template = """you receive a query: {query} and a context: {context} retrieved from a vector store. 
    You need to determine if the document is relevant to the query. """

    class Relevance(BaseModel):
        is_relevant: bool = Field(description="Whether the document is relevant to the query.")
        explanation: str = Field(description="An explanation of why the document is relevant or not.")

    is_relevant_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)

    is_relevant_content_prompt = PromptTemplate(
        template=is_relevant_content_prompt_template,
        input_variables=["query", "context"],
    )
    is_relevant_content_chain = is_relevant_content_prompt | is_relevant_llm.with_structured_output(Relevance)
    return is_relevant_content_chain

is_relevant_content_chain = create_is_relevant_content_chain()

def is_relevant_content(state):
    question = state["question"]
    context = state["context"]

    input_data = {
    "query": question,
    "context": context
}

    output = is_relevant_content_chain.invoke(input_data)
    print("Determining if the document is relevant...")
    if output["is_relevant"] == True:
        print("The document is relevant.")
        return "relevant"
    else:
        print("The document is not relevant.")
        return "not relevant"

def create_is_grounded_on_facts_chain():
    class is_grounded_on_facts(BaseModel):
        grounded_on_facts: bool = Field(description="Answer is grounded in the facts, 'yes' or 'no'")

    is_grounded_on_facts_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)
    is_grounded_on_facts_prompt_template = """You are a fact-checker that determines if the given answer {answer} is grounded in the given context {context}
    you don't mind if it doesn't make sense, as long as it is grounded in the context.
    output a json containing the answer to the question, and appart from the json format don't output any additional text.

    """
    is_grounded_on_facts_prompt = PromptTemplate(
        template=is_grounded_on_facts_prompt_template,
        input_variables=["context", "answer"],
    )
    is_grounded_on_facts_chain = is_grounded_on_facts_prompt | is_grounded_on_facts_llm.with_structured_output(is_grounded_on_facts)
    return is_grounded_on_facts_chain

def create_can_be_answered_chain():
    can_be_answered_prompt_template = """You receive a query: {question} and a context: {context}. 
    You need to determine if the question can be fully answered based on the context."""

    class QuestionAnswer(BaseModel):
        can_be_answered: bool = Field(description="binary result of whether the question can be fully answered or not")
        explanation: str = Field(description="An explanation of why the question can be fully answered or not.")

    can_be_answered_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)
    can_be_answered_chain = PromptTemplate.from_template(can_be_answered_prompt_template) | can_be_answered_llm.with_structured_output(QuestionAnswer)
    return can_be_answered_chain

def create_is_distilled_content_grounded_on_content_chain():
    is_distilled_content_grounded_on_content_prompt_template = """you receive some distilled content: {distilled_content} and the original context: {original_context}.
        you need to determine if the distilled content is grounded on the original context.
        if the distilled content is grounded on the original context, set the grounded field to true.
        if the distilled content is not grounded on the original context, set the grounded field to false."""
    

    class IsDistilledContentGroundedOnContent(BaseModel):
        grounded: bool = Field(description="Whether the distilled content is grounded on the original context.")
        explanation: str = Field(description="An explanation of why the distilled content is or is not grounded on the original context.")

    is_distilled_content_grounded_on_content_llm =ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)

    is_distilled_content_grounded_on_content_chain = PromptTemplate.from_template(is_distilled_content_grounded_on_content_prompt_template) | is_distilled_content_grounded_on_content_llm.with_structured_output(IsDistilledContentGroundedOnContent)
    return is_distilled_content_grounded_on_content_chain

is_distilled_content_grounded_on_content_chain = create_is_distilled_content_grounded_on_content_chain()

def is_distilled_content_grounded_on_content(state):
    pprint("--------------------")

    print("Determining if the distilled content is grounded on the original context...")
    distilled_content = state["relevant_context"]
    original_context = state["context"]

    input_data = {
        "distilled_content": distilled_content,
        "original_context": original_context
    }

    output = is_distilled_content_grounded_on_content_chain.invoke(input_data)
    grounded = output.grounded

    if grounded:
        print("The distilled content is grounded on the original context.")
        return "grounded on the original context"
    else:
        print("The distilled content is not grounded on the original context.")
        return "not grounded on the original context"
    
class QualitativeRetrievalGraphState(TypedDict):
    question: str
    context: str
    relevant_context: str

def create_qualitative_retrieval_book_chunks_workflow_app():
    qualitative_chunks_retrieval_workflow = StateGraph(QualitativeRetrievalGraphState)
    qualitative_chunks_retrieval_workflow.add_node("retrieve_chunks_context_per_question",retrieve_chunks_context_per_question)
    qualitative_chunks_retrieval_workflow.add_node("keep_only_relevant_content",keep_only_relevant_content)
    qualitative_chunks_retrieval_workflow.set_entry_point("retrieve_chunks_context_per_question")
    qualitative_chunks_retrieval_workflow.add_edge("retrieve_chunks_context_per_question", "keep_only_relevant_content")
    qualitative_chunks_retrieval_workflow.add_conditional_edges(
        "keep_only_relevant_content",
        is_distilled_content_grounded_on_content,
        {"grounded on the original context":END,
        "not grounded on the original context":"keep_only_relevant_content"},
        )
    return qualitative_chunks_retrieval_workflow.compile()

def create_qualitative_retrieval_chapter_summaries_workflow_app():
    qualitative_summaries_retrieval_workflow = StateGraph(QualitativeRetrievalGraphState)
    qualitative_summaries_retrieval_workflow.add_node("retrieve_summaries_context_per_question",retrieve_summaries_context_per_question)
    qualitative_summaries_retrieval_workflow.add_node("keep_only_relevant_content",keep_only_relevant_content)
    qualitative_summaries_retrieval_workflow.set_entry_point("retrieve_summaries_context_per_question")
    qualitative_summaries_retrieval_workflow.add_edge("retrieve_summaries_context_per_question", "keep_only_relevant_content")
    qualitative_summaries_retrieval_workflow.add_conditional_edges(
        "keep_only_relevant_content",
        is_distilled_content_grounded_on_content,
        {"grounded on the original context":END,
        "not grounded on the original context":"keep_only_relevant_content"},
        )
    return qualitative_summaries_retrieval_workflow.compile()

def create_qualitative_book_quotes_retrieval_workflow_app():
    qualitative_book_quotes_retrieval_workflow = StateGraph(QualitativeRetrievalGraphState)
    qualitative_book_quotes_retrieval_workflow.add_node("retrieve_book_quotes_context_per_question",retrieve_book_quotes_context_per_question)
    qualitative_book_quotes_retrieval_workflow.add_node("keep_only_relevant_content",keep_only_relevant_content)
    qualitative_book_quotes_retrieval_workflow.set_entry_point("retrieve_book_quotes_context_per_question")
    qualitative_book_quotes_retrieval_workflow.add_edge("retrieve_book_quotes_context_per_question", "keep_only_relevant_content")
    qualitative_book_quotes_retrieval_workflow.add_conditional_edges(
        "keep_only_relevant_content",
        is_distilled_content_grounded_on_content,
        {"grounded on the original context":END,
        "not grounded on the original context":"keep_only_relevant_content"},
        )
    return qualitative_book_quotes_retrieval_workflow.compile()

is_grounded_on_facts_chain = create_is_grounded_on_facts_chain()

def is_answer_grounded_on_context(state):
    print("Checking if the answer is grounded in the facts...")
    context = state["context"]
    answer = state["answer"]
    
    result = is_grounded_on_facts_chain.invoke({"context": context, "answer": answer})
    grounded_on_facts = result.grounded_on_facts
    if not grounded_on_facts:
        print("The answer is hallucination.")
        return "hallucination"
    else:
        print("The answer is grounded in the facts.")
        return "grounded on context"

def create_qualitative_answer_workflow_app():
    class QualitativeAnswerGraphState(TypedDict):
        question: str
        context: str
        answer: str

    qualitative_answer_workflow = StateGraph(QualitativeAnswerGraphState)
    qualitative_answer_workflow.add_node("answer_question_from_context",answer_question_from_context)
    qualitative_answer_workflow.set_entry_point("answer_question_from_context")
    qualitative_answer_workflow.add_conditional_edges(
    "answer_question_from_context",is_answer_grounded_on_context ,{"hallucination":"answer_question_from_context", "grounded on context":END}
    )
    return qualitative_answer_workflow.compile()

class PlanExecute(TypedDict):
    curr_state: str
    question: str
    anonymized_question: str
    query_to_retrieve_or_answer: str
    plan: List[str]
    past_steps: List[str]
    mapping: dict 
    curr_context: str
    aggregated_context: str
    tool: str
    response: str

class Plan(BaseModel):
        steps: List[str] = Field(
            description="different steps to follow, should be in sorted order"
        )

def create_plan_chain():
    planner_prompt=""" For the given query {question}, come up with a simple step by step plan of how to figure out the answer. 

    This plan should involve individual tasks, that if executed correctly will yield the correct answer. Do not add any superfluous steps. 
    The result of the final step should be the final answer. Make sure that each step has all the information needed - do not skip steps.

    """

    planner_prompt = PromptTemplate(
        template=planner_prompt,
        input_variables=["question"], 
        )

    planner_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)

    planner = planner_prompt | planner_llm.with_structured_output(Plan)
    return planner

def create_break_down_plan_chain():

    break_down_plan_prompt_template = """You receive a plan {plan} which contains a series of steps to follow in order to answer a query. 
    you need to go through the plan refine it according to this:
    1. every step has to be able to be executed by either:
        i. retrieving relevant information from a vector store of book chunks
        ii. retrieving relevant information from a vector store of chapter summaries
        iii. retrieving relevant information from a vector store of book quotes
        iv. answering a question from a given context.
    2. every step should contain all the information needed to execute it.

    output the refined plan
    """

    break_down_plan_prompt = PromptTemplate(
        template=break_down_plan_prompt_template,
        input_variables=["plan"],
    )

    break_down_plan_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)

    break_down_plan_chain = break_down_plan_prompt | break_down_plan_llm.with_structured_output(Plan)

    return break_down_plan_chain

def create_replanner_chain():
    replanner_prompt_template =""" For the given objective, come up with a simple step by step plan of how to figure out the answer. 
    This plan should involve individual tasks, that if executed correctly will yield the correct answer. Do not add any superfluous steps. 
    The result of the final step should be the final answer. Make sure that each step has all the information needed - do not skip steps.

    assume that the answer was not found yet and you need to update the plan accordingly, so the plan should never be empty.

    Your objective was this:
    {question}

    Your original plan was this:
    {plan}

    You have currently done the follow steps:
    {past_steps}

    You already have the following context:
    {aggregated_context}

    Update your plan accordingly. If further steps are needed, fill out the plan with only those steps.
    Do not return previously done steps as part of the plan.

    the format is json so escape quotes and new lines.

    """

    replanner_prompt = PromptTemplate(
        template=replanner_prompt_template,
        input_variables=["question", "plan", "past_steps", "aggregated_context"],
    )

    replanner_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)
    replanner = replanner_prompt | replanner_llm.with_structured_output(Plan)
    return replanner

def create_task_handler_chain():
    tasks_handler_prompt_template = """You are a task handler that receives a task {curr_task} and have to decide with tool to use to execute the task.
    You have the following tools at your disposal:
    Tool A: a tool that retrieves relevant information from a vector store of book chunks based on a given query.
    - use Tool A when you think the current task should search for information in the book chunks.
    Took B: a tool that retrieves relevant information from a vector store of chapter summaries based on a given query.
    - use Tool B when you think the current task should search for information in the chapter summaries.
    Tool C: a tool that retrieves relevant information from a vector store of quotes from the book based on a given query.
    - use Tool C when you think the current task should search for information in the book quotes.
    Tool D: a tool that answers a question from a given context.
    - use Tool D ONLY when you the current task can be answered by the aggregated context {aggregated_context}

    you also receive the last tool used {last_tool}
    if {last_tool} was retrieve_chunks, use other tools than Tool A.

    You also have the past steps {past_steps} that you can use to make decisions and understand the context of the task.
    You also have the initial user's question {question} that you can use to make decisions and understand the context of the task.
    if you decide to use Tools A,B or C, output the query to be used for the tool and also output the relevant tool.
    if you decide to use Tool D, output the question to be used for the tool, the context, and also that the tool to be used is Tool D.

    """

    class TaskHandlerOutput:
        query: str = Field(description="The query to be either retrieved from the vector store, or the question that should be answered from context.")
        curr_context: str = Field(description="The context to be based on in order to answer the query.")
        tool: str = Field(description="The tool to be used should be either retrieve_chunks, retrieve_summaries, retrieve_quotes, or answer_from_context.")


    task_handler_prompt = PromptTemplate(
        template=tasks_handler_prompt_template,
        input_variables=["curr_task", "aggregated_context", "last_tool" "past_steps", "question"],
    )

    task_handler_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)
    task_handler_chain = task_handler_prompt | task_handler_llm.with_structured_output(TaskHandlerOutput)
    return task_handler_chain

def create_anonymize_question_chain():
    class AnonymizeQuestion(BaseModel):
        anonymized_question : str = Field(description="Anonymized question.")
        mapping: dict = Field(description="Mapping of original name entities to variables.")
        explanation: str = Field(description="Explanation of the action.")

    anonymize_question_parser = JsonOutputParser(pydantic_object=AnonymizeQuestion)


    anonymize_question_prompt_template = """ You are a question anonymizer. The input You receive is a string containing several words that
    construct a question {question}. Your goal is to changes all name entities in the input to variables, and remember the mapping of the original name entities to the variables.
    ```example1:
            if the input is \"who is harry potter?\" the output should be \"who is X?\" and the mapping should be {{\"X\": \"harry potter\"}} ```
    ```example2:
            if the input is \"how did the bad guy played with the alex and rony?\" 
            the output should be \"how did the X played with the Y and Z?\" and the mapping should be {{\"X\": \"bad guy\", \"Y\": \"alex\", \"Z\": \"rony\"}}```
    you must replace all name entities in the input with variables, and remember the mapping of the original name entities to the variables.
    output the anonymized question and the mapping as two separate fields in a json format as described here, without any additional text apart from the json format.
   """



    anonymize_question_prompt = PromptTemplate(
        template=anonymize_question_prompt_template,
        input_variables=["question"],
        partial_variables={"format_instructions": anonymize_question_parser.get_format_instructions()},
    )

    anonymize_question_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)
    anonymize_question_chain = anonymize_question_prompt | anonymize_question_llm | anonymize_question_parser
    return anonymize_question_chain

def create_deanonymize_plan_chain():
    class DeAnonymizePlan(BaseModel):
        plan: List = Field(description="Plan to follow in future. with all the variables replaced with the mapped words.")


    de_anonymize_plan_prompt_template = """ you receive a list of tasks: {plan}, where some of the words are replaced with mapped variables. you also receive
    the mapping for those variables to words {mapping}. replace all the variables in the list of tasks with the mapped words. if no variables are present,
    return the original list of tasks. in any case, just output the updated list of tasks in a json format as described here, without any additional text apart from the
    """


    de_anonymize_plan_prompt = PromptTemplate(
        template=de_anonymize_plan_prompt_template,
        input_variables=["plan", "mapping"],
    )

    de_anonymize_plan_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)
    de_anonymize_plan_chain = de_anonymize_plan_prompt | de_anonymize_plan_llm.with_structured_output(DeAnonymizePlan)
    return de_anonymize_plan_chain

def create_can_be_answered_already_chain():
    class CanBeAnsweredAlready(BaseModel):
        can_be_answered: bool = Field(description="Whether the question can be fully answered or not based on the given context.")

    can_be_answered_already_prompt_template = """You receive a query: {question} and a context: {context}.
    You need to determine if the question can be fully answered relying only the given context.
    The only infomation you have and can rely on is the context you received. 
    you have no prior knowledge of the question or the context.
    if you think the question can be answered based on the context, output 'true', otherwise output 'false'.
    """

    can_be_answered_already_prompt = PromptTemplate(
        template=can_be_answered_already_prompt_template,
        input_variables=["question","context"],
    )

    can_be_answered_already_llm = ChatOpenAI(temperature=0, model_name="gpt-4o", max_tokens=2000)
    can_be_answered_already_chain = can_be_answered_already_prompt | can_be_answered_already_llm.with_structured_output(CanBeAnsweredAlready)
    return can_be_answered_already_chain

task_handler_chain = create_task_handler_chain()
qualitative_chunks_retrieval_workflow_app = create_qualitative_retrieval_book_chunks_workflow_app()
qualitative_summaries_retrieval_workflow_app = create_qualitative_retrieval_chapter_summaries_workflow_app()
qualitative_book_quotes_retrieval_workflow_app = create_qualitative_book_quotes_retrieval_workflow_app()
qualitative_answer_workflow_app = create_qualitative_answer_workflow_app()
de_anonymize_plan_chain = create_deanonymize_plan_chain()
planner = create_plan_chain()
break_down_plan_chain = create_break_down_plan_chain()
replanner = create_replanner_chain()
anonymize_question_chain = create_anonymize_question_chain()
can_be_answered_already_chain = create_can_be_answered_already_chain()

def run_task_handler_chain(state: PlanExecute):
    state["curr_state"] = "task_handler"
    print("the current plan is:")
    print(state["plan"])
    pprint("--------------------") 

    if not state.get('past_steps'):
        state["past_steps"] = []

    curr_task = state["plan"][0]

    inputs = {"curr_task": curr_task,
               "aggregated_context": state.get("aggregated_context", ""),
                "last_tool": state.get("tool", ""),
                "past_steps": state["past_steps"],
                "question": state["question"]}
    
    output = task_handler_chain.invoke(inputs)
  
    state["past_steps"].append(curr_task)
    state["plan"].pop(0)

    state["query_to_retrieve_or_answer"] = output.query
    state["tool"] = output.tool
    if output.tool == "answer_from_context":
        state["curr_context"] = output.curr_context
    return state  


def retrieve_or_answer(state: PlanExecute):
    state["curr_state"] = "decide_tool"
    print("deciding whether to retrieve or answer")
    tool = state.get("tool")
    if tool == "retrieve_chunks":
        return "chosen_tool_is_retrieve_chunks"
    elif tool == "retrieve_summaries":
        return "chosen_tool_is_retrieve_summaries"
    elif tool == "retrieve_quotes":
        return "chosen_tool_is_retrieve_quotes"
    elif tool == "answer_from_context":
        return "chosen_tool_is_answer"
    else:
        raise ValueError(f"Invalid tool was outputted: {tool}. Must be one of retrieve_chunks, retrieve_summaries, retrieve_quotes, or answer_from_context")  


def run_qualitative_chunks_retrieval_workflow(state):
    state["curr_state"] = "retrieve_chunks"
    print("Running the qualitative chunks retrieval workflow...")
    question = state["query_to_retrieve_or_answer"]
    inputs = {"question": question}
    output = qualitative_chunks_retrieval_workflow_app.invoke(inputs)
    if "aggregated_context" not in state or state["aggregated_context"] is None:
        state["aggregated_context"] = ""
    state["aggregated_context"] += output.get('relevant_context', '')
    return state

def run_qualitative_summaries_retrieval_workflow(state):
    state["curr_state"] = "retrieve_summaries"
    print("Running the qualitative summaries retrieval workflow...")
    question = state["query_to_retrieve_or_answer"]
    inputs = {"question": question}
    output = qualitative_summaries_retrieval_workflow_app.invoke(inputs)
    if "aggregated_context" not in state or state["aggregated_context"] is None:
        state["aggregated_context"] = ""
    state["aggregated_context"] += output.get('relevant_context', '')
    return state

def run_qualitative_book_quotes_retrieval_workflow(state):
    state["curr_state"] = "retrieve_book_quotes"
    print("Running the qualitative book quotes retrieval workflow...")
    question = state["query_to_retrieve_or_answer"]
    inputs = {"question": question}
    output = qualitative_book_quotes_retrieval_workflow_app.invoke(inputs)
    if "aggregated_context" not in state or state["aggregated_context"] is None:
        state["aggregated_context"] = ""
    state["aggregated_context"] += output.get('relevant_context', '')
    return state
   

def run_qualtative_answer_workflow(state):
    state["curr_state"] = "answer"
    print("Running the qualitative answer workflow...")
    question = state["query_to_retrieve_or_answer"]
    context = state["curr_context"]
    inputs = {"question": question, "context": context}
    output = qualitative_answer_workflow_app.invoke(inputs)
    if "aggregated_context" not in state or state["aggregated_context"] is None:
        state["aggregated_context"] = ""
    state["aggregated_context"] += output.get("answer", "")
    return state

def run_qualtative_answer_workflow_for_final_answer(state):
    state["curr_state"] = "get_final_answer"
    print("Running the qualitative answer workflow for final answer...")
    question = state["question"]
    context = state["aggregated_context"]
    inputs = {"question": question, "context": context}
    output = qualitative_answer_workflow_app.invoke(inputs)
    state["response"] = output.get("answer", "")
    return state

def anonymize_queries(state: PlanExecute):
    state["curr_state"] = "anonymize_question"
    print("state['question']: ", state['question'])
    print("Anonymizing question")
    pprint("--------------------")
    input_values = {"question": state['question']}
    anonymized_question_output = anonymize_question_chain.invoke(input_values)
    print(f'anonymized_question_output: {anonymized_question_output}')
    anonymized_question = anonymized_question_output["anonymized_question"]
    print(f'anonimized_querry: {anonymized_question}')
    pprint("--------------------")
    mapping = anonymized_question_output["mapping"]
    state["anonymized_question"] = anonymized_question
    state["mapping"] = mapping
    return state

def deanonymize_queries(state: PlanExecute):
    state["curr_state"] = "de_anonymize_plan"
    print("De-anonymizing plan")
    pprint("--------------------")
    deanonimzed_plan = de_anonymize_plan_chain.invoke({"plan": state["plan"], "mapping": state["mapping"]})
    state["plan"] = deanonimzed_plan.plan
    print(f'de-anonimized_plan: {deanonimzed_plan.plan}')
    return state

def plan_step(state: PlanExecute):
    state["curr_state"] = "planner"
    print("Planning step")
    pprint("--------------------")
    plan = planner.invoke({"question": state['anonymized_question']})
    state["plan"] = plan.steps
    print(f'plan: {state["plan"]}')
    return state

def break_down_plan_step(state: PlanExecute):
    state["curr_state"] = "break_down_plan"
    print("Breaking down plan steps into retrievable or answerable tasks")
    pprint("--------------------")
    refined_plan = break_down_plan_chain.invoke({"plan": state["plan"]})
    state["plan"] = refined_plan.steps
    return state

def replan_step(state: PlanExecute):
    state["curr_state"] = "replan"
    print("Replanning step")
    pprint("--------------------")
    inputs = {"question": state["question"], "plan": state["plan"], "past_steps": state["past_steps"], "aggregated_context": state["aggregated_context"]}
    plan = replanner.invoke(inputs)
    state["plan"] = plan.steps
    return state

def can_be_answered(state: PlanExecute):
    state["curr_state"] = "can_be_answered_already"
    print("Checking if the ORIGINAL QUESTION can be answered already")
    pprint("--------------------")
    question = state["question"]
    context = state["aggregated_context"]
    inputs = {"question": question, "context": context}
    output = can_be_answered_already_chain.invoke(inputs)
    if output.can_be_answered == True:
        print("The ORIGINAL QUESTION can be fully answered already.")
        pprint("--------------------")
        print("the aggregated context is:")
        print(text_wrap(state["aggregated_context"]))
        print("--------------------")
        return "can_be_answered_already"
    else:
        print("The ORIGINAL QUESTION cannot be fully answered yet.")
        pprint("--------------------")
        return "cannot_be_answered_yet"

def create_agent():
    
    agent_workflow = StateGraph(PlanExecute)

    agent_workflow.add_node("anonymize_question", anonymize_queries)
    agent_workflow.add_node("planner", plan_step)
    agent_workflow.add_node("break_down_plan", break_down_plan_step)
    agent_workflow.add_node("de_anonymize_plan", deanonymize_queries)
    agent_workflow.add_node("retrieve_chunks", run_qualitative_chunks_retrieval_workflow)
    agent_workflow.add_node("retrieve_summaries", run_qualitative_summaries_retrieval_workflow)
    agent_workflow.add_node("retrieve_book_quotes", run_qualitative_book_quotes_retrieval_workflow)
    agent_workflow.add_node("answer", run_qualtative_answer_workflow)
    agent_workflow.add_node("task_handler", run_task_handler_chain)
    agent_workflow.add_node("replan", replan_step)
    agent_workflow.add_node("get_final_answer", run_qualtative_answer_workflow_for_final_answer)

    agent_workflow.set_entry_point("anonymize_question")
    agent_workflow.add_edge("anonymize_question", "planner")
    agent_workflow.add_edge("planner", "de_anonymize_plan")
    agent_workflow.add_edge("de_anonymize_plan", "break_down_plan")
    agent_workflow.add_edge("break_down_plan", "task_handler")
    agent_workflow.add_conditional_edges("task_handler", retrieve_or_answer, {"chosen_tool_is_retrieve_chunks": "retrieve_chunks", "chosen_tool_is_retrieve_summaries":
                                                                            "retrieve_summaries", "chosen_tool_is_retrieve_quotes": "retrieve_book_quotes", "chosen_tool_is_answer": "answer"})
    agent_workflow.add_edge("retrieve_chunks", "replan")
    agent_workflow.add_edge("retrieve_summaries", "replan")
    agent_workflow.add_edge("retrieve_book_quotes", "replan")
    agent_workflow.add_edge("answer", "replan")
    agent_workflow.add_conditional_edges("replan",can_be_answered, {"can_be_answered_already": "get_final_answer", "cannot_be_answered_yet": "break_down_plan"})
    agent_workflow.add_edge("get_final_answer", END)

    return agent_workflow.compile()
