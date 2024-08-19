function insert_pressure_graph() {
    $.get( "/pressure_monitor-display?date=" + toXSDate(displayScheduleDate), function( svg ) {
        var newTableRow =
            "<tr id='pressureGraphRow'>" + 
            "   <td colspan='2' class='station_name'>Pressure Log</td>" + 
            "   <td colspan='24' id='pressure_graph' style='height:60px; padding:0px;'>" + 
                svg + 
            "   </td>" +
            "</tr>";

        if ($("#pressureGraphRow").length == 1)
            $("#pressureGraphRow").replaceWith(newTableRow);
        else
            $("table#stations").append(newTableRow);
    });
}

jQuery(document).ready(function(){
    if (window.location.pathname == "/") {
        if ($('#displayScheduleDate').length > 0) {
            observer = new MutationObserver(insert_pressure_graph);
            observer.observe($('#displayScheduleDate')[0], {characterData: true, childList:true, subTree: true});
        }
    }
});
