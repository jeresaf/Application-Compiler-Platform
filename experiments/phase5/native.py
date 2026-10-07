"""Exercise Xtext native language APIs; record scope rather than invent LSP scores."""
from run import AREA, command, invoke, save

if __name__ == "__main__":
    result=invoke(command("xtext",AREA/"corpora/payment.acp"),ACP_EDITOR="1")
    assert result["status"]=="PASS",result
    output=result["output"]
    assert output["nativeIssueCount"]==0,output["nativeIssueCount"]
    assert output["nativeCompletionCount"]>0,output
    assert output["nativeResolvedReferences"]>0,output
    output.pop("model",None)
    output.pop("spans",None)
    save("xtext-editor.json",result)
    print("Xtext native validation, completion, linking/navigation, usage lookup and incremental whitespace edit PASS; rename/import gates unresolved")
