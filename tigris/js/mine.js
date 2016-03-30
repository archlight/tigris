 $(function(){

    $(".sk-spinner").hide()
    $("#graph").hide()
    $('form.no-action').submit(false);


    var initialized = false
    var editor = CodeMirror.fromTextArea(document.getElementById("code"), {
        mode: {name: "python",
               version: 2,
               singleLineStringErrors: false},
        lineNumbers: true,
        indentUnit: 4,
        tabMode: "shift",
        matchBrackets: true,
        theme: "elegant"

    });

    editor.on("change", function(cm, obj){
        if (initialized && $("#save").hasClass('btn-default'))
            $("#save").toggleClass('btn-primary btn-default')
        initialized = true        
    })

    if(editor.lineCount()>4)
        editor.setValue(editor.getValue())
    else
        editor.setValue("\n#please delete below codes and paste your bug to fix\n\nfrom zipline.api import order, record, symbol\n\n\ndef initialize(context):\n\n    context.sid = symbol('AAPL')\n\n\ndef handle_data(context, data):\n    order(context.sid, 10*multiplier())\n    record(AAPL=data[context.sid].price)\n\ndef multiplier():\n    return 2\n")

    $(".datepicker").datepicker({
        format: "yyyy-mm-dd",
        daysOfWeekDisabled: "0,6",
        autoclose: true,
        todayHighlight: true
    });

    function console_display(add, remove, message){
        $(".sk-spinner").hide()
        $("#console").show()
        $("#console").empty()
        $("#console").addClass(add)
        $("#console").removeClass(remove)
        $("#console").text(message)
    }

    $(".fa-chevron-left").click(function(){
        $(".agile-list li div").hide()
        $("#summary").toggleClass("col-md-4 col-md-2");
        $("#detail").toggleClass("col-md-8 col-md-10");

    })

    $("#save").click(function() {
        name = $("#filename").val()
        $("#filename").parent().removeClass("has-error")
        $(this).next().text("")

        if(name.length){
            if(name.indexOf(" ")==-1 && name.indexOf(".")==-1){
                formdict = {
                                "fid"  : $("#fid").val(),
                                "filename": name,
                                "script"  : editor.getValue(),
                                "public"  : $("#public").prop("checked"),
                                "protected"  : $("#protected").prop("checked")
                            },
                 $.post("code", 
                        JSON.stringify(formdict),
                        function(data){
                            //console.log(data)
                            modules = []

                            if ("error" in data){
                                $("#save").next().text(data.error)
                            }
                            else if("info" in data){
                                modules = data["info"]
                                if($("#public").prop("checked")){
                                   $("#"+data["fid"]).parent().parent().attr("class", "warning-element")
                                }
                                else{
                                   $("#"+data["fid"]).parent().parent().attr("class", "success-element") 
                                }
                            }
                            else {
                                li = $('<li class="success-element"></li>')
                                div = $('<div class="agile-detail no-margin"></div>')
                                div.text(data.filename)
                                a = $('<a class="pull-right">Edit</a>')
                                a.attr("href", "code?id="+data.fid)
                                
                                li.append(div.append(a))

                                $("#codelist").prepend(li)
                                modules = data.modules    
                            } 

                            $("#dep").empty()
                            _.each(modules, function(v, k){
                                 $('<span class="label label-success"></spn>').text(v).appendTo($("#dep"))
                            })

                            $("#save").toggleClass('btn-primary btn-default')
                        },
                        'json')               
            }
            else{
                $("#filename").parent().addClass("has-error")
                $(this).next().text("filename cannot contain space and dot")                
            }
        }
        else{
            $("#filename").parent().addClass("has-error")
            $(this).next().text("filename cannot be empty")
        }

    })

    var graph

    $("#run").click(function(){

        $("#console").hide()
        $("#graph").hide()
        $(".sk-spinner").show()

        formdict = {
                        "start": $("#start").val(),
                        "end"  : $("#end").val(),
                        "fund" : $("#fund").val(),
                        "symbols":$("#symbols").val(),
                        "code" : editor.getValue(),
                        "fid"  : $("#fid").val(),
                        "useYahoo" : $("#useYahoo").prop("checked")
                   }

        $.post( "compute",
                JSON.stringify(formdict),
                function(data){

                    $("#graph").show()
                    graph = Morris.Line({
                            element: 'graph',
                            data: data,
                            xkey: 'period',
                            ykeys: ['algorithm_period_return'],
                            labels: ['return'],
                            yLabelFormat : function(y){ return (y*100).toFixed(1) + '%' },
                            gridTextSize : 10,
                            resize: true,
                            lineWidth: 1,
                            pointSize: 0.5,
                            lineColors: ["#1c84c6"],
                            pointStrokeColors: ["#1c84c6"]
                          });
        

                    graph.setData(data)
                    $("#graph").show()

                    console_display("alert-success", "alert-danger", "Algorithm run successfully")
                },
                'json'
                )
        .fail(function(err){
                    console.log(err)
                    console_display("alert-danger", "alert-success", err.responseText)
                })
    })

});